"""Quick smoke test: submit qc/MO-9000.png via the new qc_submit_image flow.

Uses QC_INFERENCE_MOCK=false to exercise the real two-phase call:
  Phase 1 — Opus extracts 'MO-9000' label from the image.
  Phase 2 — image is stored as BLOB, AI inspection runs, result printed.

Run with:
  source venv/bin/activate
  source secrets.sh
  python qc_test.py
"""

import base64
import os
os.environ.setdefault("QC_INFERENCE_MOCK", "false")

from services.qc import qc_service

operator_image = open("qc/MO-9000.png", "rb").read()
operator_b64 = f"data:image/png;base64,{base64.b64encode(operator_image).decode()}"

result = qc_service.submit_image(image_input=operator_b64, uploaded_by="test-operator")

print("decision          :", result["decision"])
print("confidence_overall:", result.get("confidence_overall"))
print("decision_reason   :", result.get("decision_reason"))
print("findings          :", len(result.get("findings", [])))
for f in result.get("findings", []):
    print(f"  [{f.get('severity')}] {f.get('finding_type')} — {f.get('description')}")

