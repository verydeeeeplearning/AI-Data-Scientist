"""CodeSecurityChecker tests — blocked patterns, warnings, path validation."""

from ds_agent.tools.code_security import CodeSecurityChecker


class TestBlockedPatterns:
    def setup_method(self):
        self.checker = CodeSecurityChecker()

    def test_os_system_blocked(self):
        result = self.checker.check("os.system('rm -rf /')")
        assert result.allowed is False
        assert any("os.system" in b for b in result.blocked_patterns)

    def test_subprocess_blocked(self):
        result = self.checker.check("subprocess.run(['ls'])")
        assert result.allowed is False

    def test_eval_blocked(self):
        result = self.checker.check("eval(user_input)")
        assert result.allowed is False

    def test_exec_blocked(self):
        result = self.checker.check("exec(code_string)")
        assert result.allowed is False

    def test_import_blocked(self):
        result = self.checker.check("__import__('os').system('pwd')")
        assert result.allowed is False

    def test_rmtree_blocked(self):
        result = self.checker.check("shutil.rmtree('/tmp/data')")
        assert result.allowed is False

    def test_requests_blocked(self):
        result = self.checker.check("requests.get('http://evil.com')")
        assert result.allowed is False

    def test_httpx_blocked(self):
        result = self.checker.check("httpx.post('http://api.example.com')")
        assert result.allowed is False

    def test_socket_blocked(self):
        result = self.checker.check("socket.connect(('1.2.3.4', 80))")
        assert result.allowed is False

    def test_safe_code_allowed(self):
        code = """
import pandas as pd
import numpy as np
df = pd.read_csv('data.csv')
print(df.shape)
print(df.describe())
"""
        result = self.checker.check(code)
        assert result.allowed is True
        assert len(result.blocked_patterns) == 0

    def test_sklearn_code_allowed(self):
        code = """
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)
print(model.score(X_test, y_test))
"""
        result = self.checker.check(code)
        assert result.allowed is True

    def test_multiple_violations(self):
        code = "os.system('x'); eval('y')"
        result = self.checker.check(code)
        assert result.allowed is False
        assert len(result.blocked_patterns) >= 2

    # SEC-08: Patterns that were previously bypassing the checker
    def test_os_popen_blocked(self):
        result = self.checker.check("import os; os.popen('echo poc').read()")
        assert result.allowed is False
        assert any("popen" in b for b in result.blocked_patterns)

    def test_pathlib_unlink_blocked(self):
        result = self.checker.check("from pathlib import Path; Path('/tmp/x').unlink()")
        assert result.allowed is False

    def test_pickle_loads_blocked(self):
        result = self.checker.check("import pickle; pickle.loads(data)")
        assert result.allowed is False

    def test_os_environ_blocked(self):
        result = self.checker.check("import os; secret = os.environ['API_KEY']")
        assert result.allowed is False

    def test_multiprocessing_blocked(self):
        result = self.checker.check("import multiprocessing; multiprocessing.Process(target=fn)")
        assert result.allowed is False

    def test_signal_blocked(self):
        result = self.checker.check("import signal; signal.signal(signal.SIGTERM, handler)")
        assert result.allowed is False

    def test_shutil_move_blocked(self):
        result = self.checker.check("import shutil; shutil.move('/a', '/b')")
        assert result.allowed is False

    def test_webbrowser_blocked(self):
        result = self.checker.check("import webbrowser; webbrowser.open('http://evil.com')")
        assert result.allowed is False

    def test_marshal_blocked(self):
        result = self.checker.check("import marshal; marshal.loads(data)")
        assert result.allowed is False

    def test_os_chmod_blocked(self):
        result = self.checker.check("import os; os.chmod('/tmp/x', 0o777)")
        assert result.allowed is False


class TestAstCheck:
    """AST-level defense-in-depth tests."""

    def setup_method(self):
        self.checker = CodeSecurityChecker()

    def test_ast_catches_subprocess_import(self):
        result = self.checker.check("import subprocess")
        assert result.allowed is False
        assert any("subprocess" in b for b in result.blocked_patterns)

    def test_ast_catches_from_shutil_import(self):
        result = self.checker.check("from shutil import copytree")
        assert result.allowed is False

    def test_ast_catches_importlib(self):
        result = self.checker.check("import importlib")
        assert result.allowed is False

    def test_ast_catches_ctypes(self):
        result = self.checker.check("import ctypes")
        assert result.allowed is False

    def test_ast_allows_safe_imports(self):
        code = "import pandas\nimport numpy\nimport sklearn"
        result = self.checker.check(code)
        assert result.allowed is True

    def test_ast_catches_from_signal(self):
        result = self.checker.check("from signal import SIGTERM")
        assert result.allowed is False

    def test_syntax_error_not_blocked(self):
        """Syntax errors don't block — regex layer still provides coverage."""
        result = self.checker.check("def foo(:")
        # No blocked patterns from AST (graceful degradation)
        assert "Code has syntax errors" not in str(result.blocked_patterns)


class TestWarningPatterns:
    def setup_method(self):
        self.checker = CodeSecurityChecker()

    def test_pip_install_warning(self):
        result = self.checker.check("!pip install pandas")
        assert result.allowed is True
        assert any("install" in w for w in result.warnings)

    def test_to_csv_warning(self):
        result = self.checker.check("df.to_csv('output.csv')")
        assert result.allowed is True
        assert len(result.warnings) > 0

    def test_while_true_warning(self):
        result = self.checker.check("while True:\n    pass")
        assert result.allowed is True
        assert any("loop" in w for w in result.warnings)

    def test_no_warnings_for_clean_code(self):
        result = self.checker.check("x = 1 + 2\nprint(x)")
        assert result.allowed is True
        assert len(result.warnings) == 0


class TestPathValidation:
    def test_valid_workspace_path(self, tmp_path):
        checker = CodeSecurityChecker(workspace_dir=tmp_path)
        assert checker.validate_path(str(tmp_path / "data.csv")) is True

    def test_traversal_blocked(self, tmp_path):
        checker = CodeSecurityChecker(workspace_dir=tmp_path)
        assert checker.validate_path(str(tmp_path / ".." / ".." / "etc" / "passwd")) is False

    def test_absolute_outside_blocked(self, tmp_path):
        checker = CodeSecurityChecker(workspace_dir=tmp_path)
        assert checker.validate_path("/etc/passwd") is False

    def test_subdirectory_allowed(self, tmp_path):
        checker = CodeSecurityChecker(workspace_dir=tmp_path)
        sub = tmp_path / "subdir" / "file.csv"
        assert checker.validate_path(str(sub)) is True

    def test_sibling_directory_blocked(self, tmp_path):
        """SEC: str(path).startswith(str(base)) was bypassed by sibling dirs."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        sibling = tmp_path / "workspace2"
        sibling.mkdir()
        checker = CodeSecurityChecker(workspace_dir=workspace)
        assert checker.validate_path(str(sibling / "secret.txt")) is False
