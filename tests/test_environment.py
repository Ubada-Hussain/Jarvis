import os
import unittest
import json
import tempfile
import shutil
from pathlib import Path

from core.environment_scanner import EnvironmentScanner
from core.environment_index import EnvironmentIndex
from core.environment_models import EnvironmentKnowledge
from core.database import EnvironmentStore

class TestEnvironmentKnowledge(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_audit.db")
        self.store = EnvironmentStore(self.db_path)
        self.index = EnvironmentIndex(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_file(self, path: str, content: str = ""):
        full_path = os.path.join(self.test_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    # Detection & Scanning Tests
    def test_project_root_detected(self):
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        self.assertEqual(kn.project_root, os.path.abspath(self.test_dir))

    def test_python_project_detected(self):
        self._create_file("requirements.txt", "fastapi==0.100.0\nrequests")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("Python", langs)
        deps = [f.value for f in kn.dependencies]
        self.assertIn("fastapi==0.100.0", deps)
        self.assertIn("requests", deps)
        frameworks = [f.value for f in kn.frameworks]
        self.assertIn("FastAPI", frameworks)

    def test_node_project_detected(self):
        pkg_json = json.dumps({"dependencies": {"react": "^18.0", "vite": "latest"}})
        self._create_file("package.json", pkg_json)
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("JavaScript/TypeScript", langs)
        frameworks = [f.value for f in kn.frameworks]
        self.assertIn("React", frameworks)
        self.assertIn("Vite", frameworks)

    def test_git_repository_detected(self):
        self._create_file(".git/HEAD", "ref: refs/heads/main")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        self.assertIsNotNone(kn.git_state)
        self.assertTrue(kn.git_state.value)
        heads = [f.value for f in kn.repositories]
        self.assertIn("ref: refs/heads/main", heads)

    # Security & Secret Protection
    def test_env_file_not_persisted(self):
        self._create_file(".env", "SECRET_KEY=12345")
        self._create_file("secret.key", "PRIVATEKEY")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        
        # We ensure they are not accidentally parsed as entry points or anything
        all_values = json.dumps(kn.model_dump())
        self.assertNotIn("SECRET_KEY", all_values)
        self.assertNotIn("PRIVATEKEY", all_values)

    # Retrieval & Index Tests
    def test_index_save_and_retrieve(self):
        self._create_file("package.json", '{"dependencies": {"express": "4.0"}}')
        
        # Scan and save
        kn = self.index.refresh(self.test_dir)
        self.assertEqual(len(kn.languages), 1)
        
        # Retrieve directly
        retrieved = self.index.get_knowledge(self.test_dir)
        self.assertIsNotNone(retrieved)
        langs = [f.value for f in retrieved.languages]
        self.assertIn("JavaScript/TypeScript", langs)
        
    def test_query_filtering(self):
        self._create_file("package.json", '{"dependencies": {"lodash": "4.0"}}')
        self._create_file("main.py", "print('hello')")
        self.index.refresh(self.test_dir)
        
        deps = self.index.query(self.test_dir, category="dependencies")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].value, "lodash@4.0")
        
        entry = self.index.query(self.test_dir, category="entry_points")
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0].value, "main.py")

    # Add 18 more tests for thorough coverage
    def test_python_poetry_detected(self):
        self._create_file("pyproject.toml", '[tool.poetry.dependencies]\nflask = "*"')
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        deps = [f.value for f in kn.dependencies]
        self.assertIn("flask (poetry)", deps)

    def test_node_yarn_detected(self):
        self._create_file("yarn.lock", "# yarn lockfile")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("JavaScript/TypeScript (Yarn)", langs)

    def test_go_project_detected(self):
        self._create_file("go.mod", "module myapp\ngo 1.20\nrequire github.com/gin-gothic/gin v1.9.0")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("Go", langs)

    def test_rust_project_detected(self):
        self._create_file("Cargo.toml", '[dependencies]\ntokio = "1.0"')
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("Rust", langs)

    def test_java_maven_detected(self):
        self._create_file("pom.xml", "<project></project>")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("Java/Kotlin (Maven)", langs)
        
    def test_java_gradle_detected(self):
        self._create_file("build.gradle", "dependencies {}")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("Java/Kotlin (Gradle)", langs)

    def test_cpp_cmake_detected(self):
        self._create_file("CMakeLists.txt", "project(myapp)")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        langs = [f.value for f in kn.languages]
        self.assertIn("C/C++", langs)

    def test_docker_service_detected(self):
        self._create_file("Dockerfile", "FROM ubuntu")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        services = [f.value for f in kn.services]
        self.assertIn("Docker", services)
        
    def test_docker_compose_detected(self):
        self._create_file("docker-compose.yml", "services:\n  db:\n    image: postgres")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        services = [f.value for f in kn.services]
        self.assertIn("Docker Compose", services)

    def test_k8s_detected(self):
        self._create_file("k8s/deployment.yaml", "kind: Deployment")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        services = [f.value for f in kn.services]
        self.assertIn("Kubernetes", services)

    def test_entry_point_index_html(self):
        self._create_file("index.html", "<html></html>")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        entry = [f.value for f in kn.entry_points]
        self.assertIn("index.html", entry)

    def test_entry_point_app_py(self):
        self._create_file("app.py", "print()")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        entry = [f.value for f in kn.entry_points]
        self.assertIn("app.py", entry)
        
    def test_entry_point_server_js(self):
        self._create_file("server.js", "console.log()")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        entry = [f.value for f in kn.entry_points]
        self.assertIn("server.js", entry)

    def test_scanner_exclusion_node_modules(self):
        self._create_file("node_modules/package.json", '{"dependencies": {"bad": "1.0"}}')
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        deps = [f.value for f in kn.dependencies]
        self.assertEqual(len(deps), 0)

    def test_scanner_exclusion_venv(self):
        self._create_file("venv/main.py", "print()")
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        entry = [f.value for f in kn.entry_points]
        self.assertEqual(len(entry), 0)

    def test_empty_directory_scan(self):
        scanner = EnvironmentScanner(self.test_dir)
        kn = scanner.scan()
        self.assertEqual(len(kn.languages), 0)
        self.assertEqual(len(kn.frameworks), 0)
        
    def test_database_persistence_update(self):
        self._create_file("package.json", '{"dependencies": {"express": "4.0"}}')
        self.index.refresh(self.test_dir)
        
        # update
        self._create_file("requirements.txt", "flask")
        kn2 = self.index.refresh(self.test_dir)
        
        langs = [f.value for f in kn2.languages]
        self.assertIn("JavaScript/TypeScript", langs)
        self.assertIn("Python", langs)

    def test_store_missing_knowledge(self):
        retrieved = self.index.get_knowledge("/tmp/nonexistent")
        self.assertIsNone(retrieved)

if __name__ == "__main__":
    unittest.main()
