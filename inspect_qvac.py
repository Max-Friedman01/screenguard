import inspect
import pkgutil

import tetherto.qvac_sdk as qvac


print("QVAC PACKAGE")
print(qvac.__file__)

print("\nPUBLIC EXPORTS")

for name in sorted(
    name for name in dir(qvac)
    if not name.startswith("_")
):
    value = getattr(qvac, name)
    print(f"{name}: {type(value).__name__}")

    if callable(value):
        try:
            print(f"  signature: {inspect.signature(value)}")
        except (TypeError, ValueError):
            pass

print("\nSUBMODULES")

for module in pkgutil.walk_packages(
    qvac.__path__,
    qvac.__name__ + ".",
):
    print(module.name)
