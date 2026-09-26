"""Fake DigiLocker for life-sim: token + issued-docs endpoints, fixture data only."""
from fastapi import FastAPI

mock_app = FastAPI(title="Mock DigiLocker")


@mock_app.post("/sso/public/oauth2/1/token")
def token():
    return {"access_token": "mock-access-RANI-001", "token_type": "Bearer",
            "expires_in": 3600}


@mock_app.get("/digilocker/issueddocs")
def issued_docs():
    return {"files": [
        {"name": "Aadhaar Card - Rani Devi", "doctype": "ADHAR",
         "issuer": "in.gov.uidai", "uri": "dg://mock/aadhaar-rani"},
        {"name": "PAN Card - Rani Devi", "doctype": "PANCR",
         "issuer": "in.gov.pan", "uri": "dg://mock/pan-rani"},
        {"name": "Udyam Registration - Rani Foods", "doctype": "UDYAM_CERT",
         "issuer": "in.gov.udyam", "uri": "dg://mock/udyam-rani",
         "reg_no": "UDYAM-TS-07-0012345"},
    ]}
