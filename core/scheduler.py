import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from core.planner import TaskGraph, TaskNode, TaskState
from core.observability import observability_manager, ObservabilityEvent
from core.a2a import A2ADispatcher, AgentMessage, MessageType, AgentStatus
from core.memory_manager import MemoryManager
from core.memory_models import EpisodicMemory
import uuid

from core.recovery import RecoveryManager, FailureCategory, RecoveryAction, RetryPolicy

class DependencyScheduler:
    """
    Executes a TaskGraph by respecting dependencies.
    Dispatches safe tasks in parallel.
    Uses Audit Logger and RecoveryManager to determine VerificationStatus-driven completion and safe retries.
    """
    def __init__(self, agents_dict: Dict[str, Any], audit_logger):
        self.agents = agents_dict
        self.audit_logger = audit_logger
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sched")
        self.active_futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        
        self.a2a_dispatcher = A2ADispatcher(self.agents, self.audit_logger)
        self.memory_manager = MemoryManager()
        self.recovery_manager = RecoveryManager(default_max_retries=2)

    def execute_graph(self, graph: TaskGraph) -> str:
        """
        Synchronously block and execute the graph until it terminates.
        """
        observability_manager.emit_event(ObservabilityEvent(
            task_id=graph.graph_id,
            event_type="GRAPH_STARTED",
            metadata={"objective": graph.objective, "node_count": len(graph.nodes)}
        ))
        
        # Publish initial graph state to observability UI
        observability_manager.runtime_state["task_graph"] = graph.to_dict()
        observability_manager.emit_event(ObservabilityEvent(event_type="GRAPH_UPDATED"))

        while True:
            with self._lock:
                self._update_states(graph)
                ready_nodes = [n for n in graph.nodes.values() if n.status == TaskState.READY]
                
                # Check for termination
                active_count = len([n for n in graph.nodes.values() if n.status in (
                    TaskState.READY, TaskState.RUNNING, TaskState.RETRYING, TaskState.RECOVERING,
                    TaskState.WAITING_FOR_CONFIRMATION, TaskState.WAITING_FOR_DEPENDENCY
                )])
                if active_count == 0:
                    break
                    
                # Dispatch READY nodes
                for node in ready_nodes:
                    node.status = TaskState.RUNNING
                    self.active_futures[node.node_id] = self.executor.submit(self._execute_node, node, graph.graph_id)
                    
                self._sync_observability(graph)
                
            time.sleep(0.5) # Poll interval
            
        # Graph execution completed. Summarize results.
        success_count = sum(1 for n in graph.nodes.values() if n.status == TaskState.COMPLETED)
        total = len(graph.nodes)
        
        self._form_episodic_memories(graph)
        
        observability_manager.emit_event(ObservabilityEvent(
            task_id=graph.graph_id,
            event_type="GRAPH_COMPLETED",
            metadata={"completed": success_count, "total": total}
        ))
        
        if success_count < total:
            return f"Task execution finished with errors. {success_count}/{total} tasks completed successfully."
        return "All tasks completed successfully."

    def _form_episodic_memories(self, graph: TaskGraph):
        """
        Phase 5: Memory Formation Policy
        Only actual observed outcomes become episodic facts. 
        Unverified or trivial tasks are ignored.
        """
        for node in graph.nodes.values():
            # Must be completed AND verified successfully
            if node.status == TaskState.COMPLETED and node.verification_status == "VERIFIED_SUCCESS":
                events = self.audit_logger.query_events(task_id=node.node_id)
                evidence = "; ".join([e.get("evidence", "") for e in events if e.get("evidence")])
                tags = ["task_graph", "verified"]
                if node.attempts > 1:
                    tags.append("recovered")
                mem = EpisodicMemory(
                    task_id=node.node_id,
                    summary=f"Agent {node.agent} completed: {node.description}",
                    outcome=node.result if node.result else "Success",
                    evidence_reference=evidence[:1000] if evidence else "Audit Log",
                    agents_involved=[node.agent],
                    tags=tags
                )
                self.memory_manager.save_episodic_memory(mem)
                
            elif node.status == TaskState.FAILED and node.verification_status == "VERIFIED_FAILURE":
                mem = EpisodicMemory(
                    task_id=node.node_id,
                    event_type="TASK_FAILURE",
                    summary=f"Agent {node.agent} failed: {node.description}",
                    outcome=node.error if node.error else "Failure",
                    evidence_reference="Audit Log",
                    agents_involved=[node.agent],
                    tags=["task_graph", "verified", "failure", "persistent"]
                )
                self.memory_manager.save_episodic_memory(mem)

    def _update_states(self, graph: TaskGraph):
        """Resolves dependencies and marks nodes as READY or BLOCKED."""
        for node in graph.nodes.values():
            if node.status == TaskState.PENDING or node.status == TaskState.WAITING_FOR_DEPENDENCY:
                deps = [graph.nodes.get(d) for d in node.dependencies if graph.nodes.get(d)]
                
                if not deps:
                    node.status = TaskState.READY
                    continue
                    
                # Check if any dependency failed or blocked
                if any(d.status in (TaskState.FAILED, TaskState.BLOCKED) for d in deps):
                    node.status = TaskState.BLOCKED
                    node.error = "Blocked by upstream dependency failure."
                    continue
                    
                # Check if ALL dependencies completed
                if all(d.status == TaskState.COMPLETED for d in deps):
                    node.status = TaskState.READY
                else:
                    node.status = TaskState.WAITING_FOR_DEPENDENCY

    def _execute_node(self, node: TaskNode, graph_id: str):
        """Thread worker that executes a specific node with Verification-First Recovery Policy."""
        agent_name = node.agent
        max_retries = node.max_retries or 2
        
        while node.attempts < max_retries:
            node.attempts += 1
            is_retry = (node.attempts > 1)
            
            if is_retry:
                node.status = TaskState.RETRYING
                observability_manager.emit_event(ObservabilityEvent(
                    task_id=graph_id,
                    event_type="RETRY_STARTED",
                    agent=agent_name,
                    metadata={"node_id": node.node_id, "attempt": node.attempts, "max_retries": max_retries}
                ))
            else:
                observability_manager.emit_event(ObservabilityEvent(
                    task_id=graph_id,
                    event_type="NODE_STARTED",
                    agent=agent_name,
                    metadata={"node_id": node.node_id, "description": node.description}
                ))
            
            req_msg = AgentMessage(
                message_id=str(uuid.uuid4()),
                task_id=graph_id,
                node_id=node.node_id,
                sender_agent="Scheduler",
                recipient_agent=agent_name,
                message_type=MessageType.TASK_RETRYING if is_retry else MessageType.TASK_REQUEST,
                status=AgentStatus.RETRYING if is_retry else AgentStatus.PENDING,
                result=node.description,
                attempt=node.attempts
            )
            
            try:
                # Dispatch execution to target agent
                resp_msg = self.a2a_dispatcher.dispatch(req_msg)
                node.result = resp_msg.result
                
                # Check if successful execution verified
                if resp_msg.status == AgentStatus.COMPLETED:
                    node.status = TaskState.COMPLETED
                    node.verification_status = "VERIFIED_SUCCESS"
                    node.error = ""
                    
                    if is_retry:
                        self.audit_logger.log_recovery_event(
                            task_id=graph_id,
                            node_id=node.node_id,
                            agent=agent_name,
                            attempt=node.attempts,
                            failure_category=node.failure_category or "NONE",
                            recovery_action="RETRY_SUCCESS",
                            reason=f"Recovered successfully on attempt {node.attempts}.",
                            outcome="VERIFIED_SUCCESS"
                        )
                        observability_manager.emit_event(ObservabilityEvent(
                            task_id=graph_id,
                            event_type="RETRY_COMPLETED",
                            agent=agent_name,
                            status="COMPLETED",
                            metadata={"node_id": node.node_id, "attempt": node.attempts}
                        ))
                    break
                    
                else:
                    # Failure encountered — classify and determine recovery action
                    error_msg = str([e.message for e in resp_msg.errors]) if resp_msg.errors else (node.result or "Task failed")
                    error_code = resp_msg.errors[0].code if resp_msg.errors else "UNKNOWN"
                    permission_status = "DENIED" if resp_msg.status == AgentStatus.BLOCKED or "PERMISSION_DENIED" in error_code else "GRANTED"
                    
                    category = self.recovery_manager.classify_failure(
                        error_code=error_code,
                        error_msg=error_msg,
                        verification_status="VERIFIED_FAILURE" if resp_msg.status == AgentStatus.FAILED else "UNVERIFIED",
                        permission_status=permission_status
                    )
                    node.failure_category = category.value
                    
                    decision = self.recovery_manager.evaluate_recovery(
                        category=category,
                        current_attempt=node.attempts,
                        max_retries=max_retries,
                        risk_level=node.risk_level
                    )
                    
                    self.audit_logger.log_recovery_event(
                        task_id=graph_id,
                        node_id=node.node_id,
                        agent=agent_name,
                        attempt=node.attempts,
                        failure_category=category.value,
                        recovery_action=decision.action.value,
                        reason=decision.reason,
                        outcome="RETRYING" if decision.should_retry else "TERMINATED"
                    )
                    
                    if decision.should_retry and node.attempts < max_retries:
                        observability_manager.emit_event(ObservabilityEvent(
                            task_id=graph_id,
                            event_type="RECOVERY_STARTED",
                            agent=agent_name,
                            metadata={
                                "node_id": node.node_id,
                                "failure_category": category.value,
                                "action": decision.action.value,
                                "delay_s": decision.retry_delay_s
                            }
                        ))
                        if decision.retry_delay_s > 0:
                            time.sleep(decision.retry_delay_s)
                        continue
                    else:
                        if resp_msg.status == AgentStatus.BLOCKED or category == FailureCategory.PERMISSION_DENIED:
                            node.status = TaskState.BLOCKED
                        else:
                            node.status = TaskState.FAILED
                        node.verification_status = "VERIFIED_FAILURE"
                        node.error = error_msg
                        
                        observability_manager.emit_event(ObservabilityEvent(
                            task_id=graph_id,
                            event_type="RECOVERY_FAILED",
                            agent=agent_name,
                            status=node.status.value,
                            error=error_msg,
                            metadata={"node_id": node.node_id, "attempts": node.attempts}
                        ))
                        break
                        
            except Exception as e:
                node.status = TaskState.FAILED
                node.verification_status = "VERIFIED_FAILURE"
                node.error = f"Execution exception: {str(e)}"
                break
                
        observability_manager.emit_event(ObservabilityEvent(
            task_id=graph_id,
            event_type="NODE_COMPLETED" if node.status == TaskState.COMPLETED else "NODE_FAILED",
            agent=agent_name,
            status=node.status.value,
            error=node.error,
            metadata={"node_id": node.node_id, "attempts": node.attempts}
        ))
            
        observability_manager.emit_event(ObservabilityEvent(
            task_id=graph_id,
            event_type="NODE_COMPLETED" if node.status == TaskState.COMPLETED else "NODE_FAILED",
            agent=agent_name,
            status=node.status.value,
            error=node.error,
            metadata={"node_id": node.node_id}
        ))

    def _sync_observability(self, graph: TaskGraph):
        # Update the UI graph rendering state
        observability_manager.runtime_state["task_graph"] = graph.to_dict()
        observability_manager.emit_event(ObservabilityEvent(event_type="GRAPH_UPDATED"))
