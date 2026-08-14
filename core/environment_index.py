import json
from typing import List, Optional

from core.database import EnvironmentStore
from core.environment_scanner import EnvironmentScanner
from core.environment_models import EnvironmentKnowledge, EnvironmentFact
from core.observability import observability_manager, ObservabilityEvent

class EnvironmentIndex:
    """
    Central manager for Environment Knowledge.
    Provides scanning, refreshing, and structured querying.
    """
    def __init__(self, db_path: str = "audit.db"):
        self.store = EnvironmentStore(db_path)
        self.observability = observability_manager

    def get_knowledge(self, project_root: str) -> Optional[EnvironmentKnowledge]:
        data = self.store.get_environment(project_root)
        if data:
            return EnvironmentKnowledge(**data)
        return None

    def refresh(self, project_root: str) -> EnvironmentKnowledge:
        """
        Scans the project root, updates the index, and logs events.
        """
        self.observability.emit_event(ObservabilityEvent(
            event_type="ENVIRONMENT_SCAN_STARTED",
            metadata={"description": f"Started environment scan for {project_root}"}
        ))
        
        try:
            scanner = EnvironmentScanner(project_root)
            existing = self.get_knowledge(project_root)
            
            new_knowledge = scanner.scan(existing)
            
            success = self.store.save_environment(new_knowledge)
            if success:
                self.observability.emit_event(ObservabilityEvent(
                    event_type="ENVIRONMENT_INDEX_UPDATED",
                    metadata={"description": f"Successfully updated environment index for {project_root}"}
                ))
                self.observability.emit_event(ObservabilityEvent(
                    event_type="ENVIRONMENT_SCAN_COMPLETED",
                    metadata={"description": f"Completed environment scan for {project_root}"}
                ))
                return new_knowledge
            else:
                raise Exception("Failed to save to EnvironmentStore")
                
        except Exception as e:
            self.observability.emit_event(ObservabilityEvent(
                event_type="ENVIRONMENT_SCAN_FAILED",
                error=str(e),
                metadata={"description": f"Failed to scan environment: {e}"}
            ))
            raise e

    def query(self, project_root: str, category: str = None) -> List[EnvironmentFact]:
        """
        Queries the environment index for facts.
        """
        self.observability.emit_event(ObservabilityEvent(
            event_type="ENVIRONMENT_QUERY",
            metadata={"description": f"Queried environment index for category '{category}' in {project_root}"}
        ))
        
        knowledge = self.get_knowledge(project_root)
        if not knowledge:
            return []
            
        facts = []
        if category == "languages" or not category:
            facts.extend(knowledge.languages)
        if category == "frameworks" or not category:
            facts.extend(knowledge.frameworks)
        if category == "dependencies" or not category:
            facts.extend(knowledge.dependencies)
        if category == "entry_points" or not category:
            facts.extend(knowledge.entry_points)
        if category == "services" or not category:
            facts.extend(knowledge.services)
        if category == "repositories" or not category:
            facts.extend(knowledge.repositories)
        if category == "git" and knowledge.git_state:
            facts.append(knowledge.git_state)
            
        return facts
