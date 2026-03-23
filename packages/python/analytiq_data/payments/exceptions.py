"""
Payment / SPU exceptions shared by analytiq_data and app routes.

Kept in analytiq_data (not app.routes.payments) to avoid circular imports:
analytiq_data package init loads llm before common; importing app pulls auth
which expects ad.common to exist.
"""


class SPUCreditException(Exception):
    """
    Raised when an organization has insufficient SPU credits to complete an operation.

    This exception should be caught at the API level and converted to HTTP 402 Payment Required.
    """

    def __init__(self, org_id: str, required_spus: int, available_spus: int = 0):
        self.org_id = org_id
        self.required_spus = required_spus
        self.available_spus = available_spus

        message = (
            f"Insufficient SPU credits for organization {org_id}. "
            f"Required: {required_spus}, Available: {available_spus}"
        )
        super().__init__(message)
