import re

path = "/app/remediation/safety.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = '''    def get_audit_log(self) -> list[dict[str, Any]]:
        return self.state.audit_log'''

new = '''    def get_audit_log(self) -> list[dict[str, Any]]:
        if self.persist:
            return audit_store.load_audit_log()
        return self.state.audit_log'''

if old not in content:
    print("PATTERN NOT FOUND - abort")
else:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("PATCHED OK")
