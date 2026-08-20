import aiohttp

URL = "https://mobile.nectr.com.au/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "App-Version": "2.9.0"
}

class NectrApiClient:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.token = None

    async def _post(self, session, payload):
        headers = HEADERS.copy()
        if self.token:
            headers["Authorization"] = f"bearer {self.token}"
        async with session.post(URL, json=payload, headers=headers) as response:
            data = await response.json()
            if "errors" in data and not self.token:
                raise ValueError(f"GraphQL Error: {data['errors']}")
            return data.get("data", {})

    async def authenticate(self, session):
        payload = {
            "operationName": "emailAuthenticate",
            "variables": {"email": self.email, "password": self.password},
            "query": "mutation emailAuthenticate($email: String!, $password: String!) { emailAuthenticate(email: $email, password: $password) { token refreshToken __typename } }"
        }
        data = await self._post(session, payload)
        if not data or "emailAuthenticate" not in data:
            raise ValueError("Authentication failed")
        self.token = data["emailAuthenticate"]["token"]
        return self.token

    async def get_accounts(self, session):
        payload = {
            "operationName": "getUserBrief",
            "variables": {},
            "query": "query getUserBrief { userBrief { accounts { lnspId number status address state supplyStatus __typename } __typename } }"
        }
        data = await self._post(session, payload)
        return [acc for acc in data.get("userBrief", {}).get("accounts", []) if acc.get("status") == "ACTIVE"]

    async def get_usage(self, session, account_number):
        payload = {
            "operationName": "getUsageInfo",
            "variables": {
                "isSmartMeterUser": True,
                "accountNumber": account_number,
                "pageNumber": 1,
                "granularity": "HOURLY",
                "toDate": "",
                "fromDate": ""
            },
            "query": "query getUsageInfo($accountNumber: String!, $isSmartMeterUser: Boolean!, $pageNumber: Int!, $granularity: GRANUALRITY, $fromDate: String!, $toDate: String!) { getUsageInfo(accountNumber: $accountNumber, isSmartMeterUser: $isSmartMeterUser, pageNumber: $pageNumber, granularity: $granularity, fromDate: $fromDate, toDate: $toDate) { secondaryHeader allUsage { controlLoadCost controlLoadUsage exportCost exportUsage gridUsage gridCost period __typename } gridConsumption { value } exportGridConsumption { value } controlledLoadConsumption { value } __typename } }"
        }
        data = await self._post(session, payload)
        return data.get("getUsageInfo", {})

    async def get_account_info(self, session, account_number):
        payload = {
            "operationName": "getAccountInfo",
            "variables": {"accountNumber": account_number},
            "query": "query getAccountInfo($accountNumber: String!) { accountInfo(accountNumber: $accountNumber) { accountStatus isSmartMeterUser planName currentBillingPeriodStartDate currentBillingPeriodEndDate isOnSupply isControlledLoad powerFlowType accountType } }"
        }
        data = await self._post(session, payload)
        return data.get("accountInfo", {})

    async def get_power_perks(self, session, account_number):
        payload = {
            "operationName": "GetPowerPerks",
            "variables": {"accountNumber": account_number},
            "query": "query GetPowerPerks($accountNumber: String) { powerPerks(accountNumber: $accountNumber) { creditAmount percentage isRedemptionReady statusText } }"
        }
        data = await self._post(session, payload)
        return data.get("powerPerks", {})

    async def get_bill_payment_info(self, session, account_number):
        payload = {
            "operationName": "userLatestBillPaymentInfo",
            "variables": {"accountNumber": account_number},
            "query": "query userLatestBillPaymentInfo($accountNumber: String!) { userLatestBillPaymentInfo(accountNumber: $accountNumber) { balance eligibleToDeferPayment directDebitAmount directDebitDate nextScheduledPaymentDate totalDue } }"
        }
        data = await self._post(session, payload)
        return data.get("userLatestBillPaymentInfo", {})

    async def get_product_info(self, session, account_number):
        payload = {
            "operationName": "getMyProductInfo",
            "variables": {"accountNumber": account_number},
            "query": "query getMyProductInfo($accountNumber: String!) { myProductInfo(accountNumber: $accountNumber) { validFrom isEligibleForUpdate isOnBestOffer nmi features { text key value subFeature { key value } } } }"
        }
        data = await self._post(session, payload)
        return data.get("myProductInfo", {})