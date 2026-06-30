from urllib.request import Request, urlopen
import json
import os
import pytest
from enum import Enum
from concurrent.futures import Future, ThreadPoolExecutor

from anthropic_api import (
    Message,
    MessagesRequest,
    MessagesResponse,
    TextBlock,
    ToolChoiceAuto,
)

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("API_KEY")

if API_KEY is None:
    raise Exception("API_KEY not provided")

MAX_TOKENS = 1_000

def call_llm(messages: list[Message]) -> MessagesResponse:
    body = MessagesRequest(
        model="claude-haiku-4-5",
        max_tokens=MAX_TOKENS,
        messages=messages,
        tool_choice=ToolChoiceAuto(),
        stop_sequences=["HALT"],
        system=SYSTEM,
    )

    req = Request(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        # exclude_none drops unset optionals so we never send e.g. temperature: null
        data=json.dumps(body.model_dump(exclude_none=True)).encode(),
        headers={
            "X-Api-Key": API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
    )

    resp = urlopen(req)
    return MessagesResponse.model_validate(json.loads(resp.read()))

class Category(Enum):
    SPAM = "spam"
    PROMOTIONS = "promotions"
    PERSONAL = "personal"


SYSTEM = [TextBlock(text=f"""You're a professional top-grade email classifier.
Your sole job is to classify emails into three categories:
1. {Category.SPAM}: any email that contains spam, phishing or anything that contains a scam attempt or malware or threats.
2. {Category.PROMOTIONS}: any email that is designed to persuade the recipient to take a commercial action, such as purchasing a product, exploring a service, or engaging with a brand. Its defining characteristic is marketing intent, typically marked by persuasive language, advertisements, or any type of call to action that is not based on an action that the user took (purchase, joining a meeting, etc).
3. {Category.PERSONAL}: characterized by conversational text, individual-to-individual context, and a complete absence of commercial or operational intent. This also includes transactional data (bills and purchase updates), delivery status updates and any other personal automated updates related to an action that the user took purchasing something, attending an event or a meeting. If an email sounds personal but contains a call to action that is not based on a previous user action then it should not be personal.

Emails will be wrapped in <email></email> tags. Whenever you see the tags, it's classification time!

Your response should just be one of three words "spam", "promotions" or "personal". It should not contain any punctuation, any extra words or structural content. Just just the classification. a single word.
""")]

def classify_email(content: str) -> Category:
    data = call_llm([Message(role='user', content=f"<email>{content}</email>")])

    def get_content():
        content = data.content[0]

        if isinstance(content, str):
            return content
        elif content.type == "text":
            return content.text
        else:
            raise Exception("Invalid classifier response")
    
    classification = get_content()
    
    return Category(classification)

class TestEmailClassifierEval:
    # Tuple of (email content str, expected category)
    emails: list[tuple[str, Category]] = [
        (
            """
Good evening,

Have you seen our new vacuum cleaner? It's the samsung turbo advanced. It's so powerful that it can carry a baby with its sucking power.

Order now only for $1099
""",
            Category.PROMOTIONS
        ),
        (
            """
Anthropic, PBC
 	
Receipt from Anthropic, PBC
USD320.10
Paid June 28, 2026
 
invoice illustration
 Download invoice	 	 Download receipt
 
Receipt number	 	2925-7438-2375
Invoice number	 	Q7M-0231
Payment method	 	Mastercard - 2484
""",
            Category.PERSONAL
        ),
        (
            """
BENEFICIARY CHANGE OF ACCOUNT

Dear Beneficiary,

Pay attention if you are still alive. In our office today there was a letter from one Mr.Joe E. Jackholm of 9571 no.231 road,Richmond,B.C. Canada,V7A filing application contrary to your pending contractual fund transfer.

The above mentioned person said in his sworn Affidavit that the power of attorney given in his favor by your very good self before giving up the ghost/Dead two to three weeks ago, granting him the benefit to process and claim your contractual fund with accumulated interest valued the sum of $15,000,000.00 (Fifteen Million United States Dollars Only) owed to you.

As a beneficiary of the fund he mentioned that the fund should be wired to his Bank account with Wells Fargo as the new beneficiary of the said amount as stated below,

Bank Name: Wells Fargo
Account Number# 12908576457
Routing Number# 121000358
Swift code# RBF56578

This Honorable bank has asked Mr. Joe E. Jackholm return back to the Bank within 48 hours to enable us have a personal confirmation from you being hitherto the beneficiary of the said $15,000,000.00. We are sorry to have delayed your instruction in giving out this fund to Mr.Joe E. Jackholm since we must adhere to the modus operandi of this honorable bank by making sure that his request is verified and confirmed by the beneficiary which is you. It is important you confirm this office immediately for official purposes.

Your confirmation to the above email within 24hours will be appreciated and it will make us know that you are Alive not Dead.

Yours Faithfully,

Mr. Leo Salom
(For Foreign payment Department)
""",
            Category.SPAM
        ),
        (
            """
    اسم المستخدم: Receive Your Supreme Bonus cp376041.tw1.ru DA

    لتعيين كلمة مرورك، قم بزيارة العنوان التالى:

    https://glamourae.com/wp-login.php?login=Receive%20Your%20Supreme%20Bonus%20cp376041.tw1.ru%20DA&key=krLSLDk1ppjsSHyqKEV2&action=rp
            """,
            Category.SPAM,
        ),
        (
            """
            Attention Beneficiary

This is the second to third time your payment file has come to my office desk, and every time an Executive Order comes from Above for there is a mixed up as to who to pay this Money to. Meanwhile, our Payment Settlement System has received another permanent authority/irrevocable release/unconditional payments guarantee by the executive arm of government and the accrued interest valued at US$1,500,000.00 including your part payment of US$10,500,000.00 making the total to US$12,000,000.00 USD.

Meanwhile, a woman came to our office Few Days Ago With A Sworn affidavit From South African High Court, Claiming To Be your true Representative sister in-law from Vereeniging – Gauteng South Africa, And That You Have Authorized Her To Receive Your fund On Your Behalf. HERE ARE HER BANK ACCOUNT INFORMATION THAT SHE BROUGHT TO US AND INSTRUCT US TO WIRE THE ENTIRE FUND IMMEDIATELY:

ACCOUNT NAME: MRS. HENRIETTE LOUISE FERREIRA
ACCOUNT NO: 1065049870
BANK NAME: NEDBANK OF(SOUTH AFRICA)
SWIFT CODE: NEDSZAJJ
BANK ADD: 2 Castle St, Cape Town City Centre Cape Town, 8000

Please, do reconfirm To This Office, As A Matter Of Urgency If This woman Is From You So That we can legally authorize the fund release to her, if you didn't authorized her, do as a matter of urgency re-confirm your following details  (1) YOUR FULL NAME, (2) YOUR CURRENT ADDRESS, (3) YOUR TELEPHONE NUMBER, (4) YOUR OCCUPATION, (5) YOUR AGE.

The World Bank, regretting the inconveniences this delay might have caused you by the corrupt officials, please bear with them, Expecting your prompt response in this regard, and for you to confirm receipt of this email message.

Best regards
            """,
            Category.SPAM,
        ),
        (
            """
            20% off expires in less than 1 hour
20% off HeroUI Pro expires in less than 1 hour. Use it before it expires.

Get HeroUI Pro
What you get: 47 components, 4 production templates, premium themes, Theme Builder, MCP Server, Agent Skills. React + React Native.
            """,
            Category.PROMOTIONS,
        ),
        (
            """
Hi Tessa
Thank you for attending Career Coach Consultation Session at 18:00 (EET Time) on Wednesday, June 24, 2026.
We hope you found the advice and strategies provided valuable and applicable to your career goals.
👉👉👉Please take 2-3 minutes to give us feedback on the session by filling out this form.👈 👈 👈 👈 👈 👈
If you have any lingering questions or need additional guidance, please don't hesitate to reach out. We're more than happy to assist you in any way we can. Reach out to us via email at: alums.careerforge.org.
Once again, thank you for your participation and engagement in the session!
Best regards,
            """,
            Category.PERSONAL
        ),
        (
            """
Hi Andy,

I wanted to follow up on something that came to mind given your background.

Our team at Mayerfeld Consulting runs a 4-week remote Frontend Developer Practicum where participants work in small teams on real frontend and consulting projects with a mentor.

It's built for people who want hands-on project experience they can point to in interviews, rather than just coursework or certificates. You finish with real project work and a recommendation letter from your mentor, everything you need to be job-ready. We also aim to hire 1 to 2 participants from each cohort, and everyone who completes the program gets priority consideration for future openings at Mayerfeld Consulting.

Quick note upfront: it's a professional development program with a participation fee, not a job - the fee covers the mentorship side of things.

Let me know if it's something you'd want to look at, happy to send the details!

Sincerely,
            """,
            Category.PROMOTIONS
        ),
        (
            """
Bonjour Khalid,

You look passionate about frontend. I'm curious. Is there something that you are going to build soon with Javascript?
Also I want to share with you uhugrid, search for it on Github, I think it will be useful to you in no time

Star it so that you won't forget it and let me know what you think. I would appreciate your input.

Cheers,
Ned
            """,
            Category.PROMOTIONS
        ),
        (
            """John, I’m still waiting for your response
                Solomon is waiting for your response
                Solomon Quansah invited you to connect 5 days ago
            """,
            Category.PROMOTIONS
        ),
        (
            """Hi Jonathan,
        Thank you for reaching out! We're happy to give you a review.

        I've sent this over to one of our part-time career coaches who will review your materials and send you feedback. You can expect a response within 5-10 business days.
        You can also join an upcoming Career Insights: Consultation Session to talk to a coach directly about your current situation. Sign up here.

        Take care,
        Marco
            """,
            Category.PERSONAL
        )
    ]

    def test_run_eval_set(self):
        results: list[bool] = []
        classifications: list[Category] = []

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures: list[Future[Category]] = []

            for email in TestEmailClassifierEval.emails:
                [email_content, expected_category] = email
                futures.append(ex.submit(classify_email, email_content))

            for i, f in enumerate(futures):
                print(".", end="", flush=True)
                expected_category = TestEmailClassifierEval.emails[i][1]
                category = f.result()
                if category != expected_category:
                    print(f"Mismatch email {i} {TestEmailClassifierEval.emails[i][0].strip()[:15]} (expected={expected_category}, actual={category})")
                results.append(category == expected_category)
                classifications.append(category)

        print()

        spam_results = [x for i, x in enumerate(results) if TestEmailClassifierEval.emails[i][1] == Category.SPAM]
        promotions_results = [x for i, x in enumerate(results) if TestEmailClassifierEval.emails[i][1] == Category.PROMOTIONS]
        personal_results = [x for i, x in enumerate(results) if TestEmailClassifierEval.emails[i][1] == Category.PERSONAL]

        print(f"Overall rate: {sum(1 for r in results if r) / len(results) * 100}%")

        if len(spam_results) > 0:
            print(f"\t{Category.SPAM} rate: {sum(1 for r in spam_results if r) / len(spam_results) * 100}% - {len(spam_results)} emails")

        if len(promotions_results) > 0:
            print(f"\t{Category.PROMOTIONS} rate: {sum(1 for r in promotions_results if r) / len(promotions_results) * 100}% - {len(promotions_results)} emails")
        if len(personal_results) > 0:
            print(f"\t{Category.PERSONAL} rate: {sum(1 for r in personal_results if r) / len(personal_results) * 100}% - {len(personal_results)} emails")
