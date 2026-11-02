# Deployment and secure handoff

## What can be demonstrated without credentials

This product is intentionally offline-first. It uses the versioned market-data cache in `data/`, so its complete advisor workflow runs locally or on Streamlit Community Cloud without API keys, client-account access, or third-party AI calls.

## Streamlit Community Cloud

1. Create a GitHub repository and upload this project **without** `.env`, `.streamlit/secrets.toml`, raw client data, or real tax returns.
2. In Streamlit Community Cloud, choose the repository, branch, and `app.py`.
3. Deploy. No secret is needed for the supplied competition demo.
4. Test the public URL with the default demo persona in an incognito/private browser window.

## Secure production boundary

- Do not enter real client PII into the competition build.
- Do not commit credentials, account exports, tax returns, or signed proposals.
- Any future data connector must use host-managed secrets, role-based access, encrypted storage, consent controls, retention/deletion policies, and compliance review.
- The current cached proxy data is for reproducible demonstration, not licensed production reporting.

## Pre-demo command

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python validate_submission.py
streamlit run app.py
```


