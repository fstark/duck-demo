"""Quick smoke test: send reference + qc/MO-9000.png to the inference API (identical to the app call)."""

import base64
import config
from services import myforterro


def _img_uri(path: str) -> str:
    data = open(path, "rb").read()
    b64 = base64.b64encode(data).decode()
    return f"data:image/png;base64,{b64}"


reference_uri = _img_uri("images/ELVIS-DUCK-20CM.png")
operator_uri = _img_uri("qc/MO-9000.png")

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "You are a quality control inspector for rubber duck manufacturing. "
                    "Compare the reference product image (first) with the submitted batch image (second). "
                    "Identify any defects or quality issues. "
                    "Respond ONLY with a valid JSON object matching this schema exactly:\n"
                    '{"decision": "pass|partial_scrap|full_scrap", '
                    '"confidence_overall": <float 0-1>, '
                    '"decision_reason": "<string>", '
                    '"findings": [{"type": "<finding_type>", "severity": "<severity>", '
                    '"confidence": <float 0-1>, "description": "<string>", '
                    '"image_ref": null, "location_hint": null}]}\n'
                    "finding_type must be one of: wrong_product, paint_defect, shape_defect, "
                    "assembly_defect, packaging_defect, missing_part. "
                    "severity must be one of: critical, major, minor. "
                    "decision: pass=all good, partial_scrap=some defects, full_scrap=all defective."
                ),
            },
            {"type": "image_url", "image_url": {"url": reference_uri}},
            {"type": "image_url", "image_url": {"url": operator_uri}},
        ],
    }
]

resp = myforterro.chat_completion(model=config.QC_INFERENCE_MODEL, messages=messages)
print(repr(resp.choices[0].message.content))
