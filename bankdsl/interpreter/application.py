import json
from dataclasses import dataclass, field


@dataclass
class Application:
    applicant_name: str
    product_name: str
    product_version: str
    requested_amount: float
    requested_term: int
    data: dict = field(default_factory=dict)

    def get(self, field_name):
        return self.data.get(field_name) #vraca iz tog dict , ako nema None

    @staticmethod
    def from_json_file(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return Application(
            applicant_name=raw["applicant_name"],
            product_name=raw["product_name"],
            product_version=raw["product_version"],
            requested_amount=raw["requested_amount"],
            requested_term=raw["requested_term"],
            data=raw.get("data", {}),
        )

    @staticmethod
    def from_dict(raw):
        return Application(
            applicant_name=raw["applicant_name"],
            product_name=raw["product_name"],
            product_version=raw["product_version"],
            requested_amount=raw["requested_amount"],
            requested_term=raw["requested_term"],
            data=raw.get("data", {}),
        )
