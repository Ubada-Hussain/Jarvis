import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from core.planner import TaskGraph, TaskNode, TaskState
from core.observability import observability_manager, ObservabilityEvent
from core.a2a import A2ADispatcher, AgentMessage, MessageType, AgentStatus
from core.memory_manager import MemoryManager
from core.memory_models import EpisodicMemory
import uuid

class DependencyScheduler:
    """
    Executes a TaskGraph by respecting dependencies.
    Dispatches safe tasks in parallel.
    Uses Audit Logger to determine VerificationStatus-driven completion.
    """
    def __init__(self, agents_dict: Dict[str, Any], audit_logger):
        self.agents = agents_dict
        self.audit_logger = audit_logger
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sched")
        self.active_futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        
        self.a2a_dispatcher = A2ADispatcher(self.agents, self.audit_logger)
        self.memory_manager = MemoryManager()

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
                active_count = len([n for n in graph.nodes.values() if n.status in (TaskState.READY, TaskState.RUNNING, TaskState.WAITING_FOR_CONFIRMATION, TaskState.WAITING_FOR_DEPENDENCY)])
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
                mem = EpisodicMemory(
                    task_id=node.node_id,
                    summary=f"Agent {node.agent} completed: {node.description}",
                    outcome=node.result if node.result else "Success",
                    evidence_reference=evidence[:1000] if evidence else "Audit Log",
                    agents_involved=[node.agent],
                    tags=["task_graph", "verified"]
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
                    tags=["task_graph", "verified", "failure"]
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
        """Thread worker that executes a specific node via A2A protocol."""
        agent_name = node.agent
        
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
            message_type=MessageType.TASK_REQUEST,
            status=AgentStatus.PENDING,
            result=node.description
        )
        
        try:
            # The A2A Dispatcher handles the native execution, evidence extraction, 
            # and returns a final TASK_RESULT/TASK_FAILED message.
            resp_msg = self.a2a_dispatcher.dispatch(req_msg)
            
            node.result = resp_msg.result
            
            # Map AgentStatus to TaskState
            if resp_msg.status == AgentStatus.COMPLETED:
                node.status = TaskState.COMPLETED
                node.verification_status = "VERIFIED_SUCCESS"
            elif resp_msg.status == AgentStatus.FAILED:
                node.status = TaskState.FAILED
                node.verification_status = "VERIFIED_FAILURE"
                node.error = str([e.message for e in resp_msg.errors])
            elif resp_msg.status == AgentStatus.BLOCKED:
                node.status = TaskState.BLOCKED
                node.error = str([e.message for e in resp_msg.errors])
            else:
                node.status = TaskState.FAILED
                node.error = f"Unexpected A2A status: {resp_msg.status}"
                
        except Exception as e:
            node.status = TaskState.FAILED
            node.error = f"Execution exception: {str(e)}"
            
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
