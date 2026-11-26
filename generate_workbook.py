import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

wb = openpyxl.Workbook()

HEADER_FILL = PatternFill(start_color="1B4332", end_color="1B4332", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="D8F3DC", end_color="D8F3DC", fill_type="solid")
INPUT_FILL = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
BOLD_FONT = Font(bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14, color="1B4332")
WRAP = Alignment(wrap_text=True, vertical="top")


def style_headers(ws, row_num=1):
    for cell in ws[row_num]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")


def auto_fit(ws, widths):
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width


# Tab 1: Channel Comparison
ws1 = wb.active
ws1.title = "Channel Comparison"
ws1.append(["Attribute", "Email (Brevo)", "SMS (Termii / Africa's Talking)", "WhatsApp (Business API)"])
style_headers(ws1, 1)

comparison_rows = [
    ("Reach in Nigeria", "Moderate — high among corporate/hotel guests and smartphones, lower among rural/older school parents.", "Highest (99%+) — works on every feature phone and smartphone without mobile data.", "High among smartphone users, but requires internet data and WhatsApp installed."),
    ("Cost per Message", "Free up to 300 emails/day on Brevo; ~₦0.50–₦1.50/email on paid plans.", "~₦4.00–₦6.50 per 160-char GSM-7 page on DND routes (doubles if >160 chars or contains emojis).", "~₦15–₦45+ per marketing/utility conversation (Meta template pricing + BSP markup)."),
    ("Setup & Approval Time", "Fast (1 day) — verify domain SPF/DKIM records and plug in Brevo API key.", "3–7 business days — requires CAC/ID KYC and Alphanumeric Sender ID registration on Termii.", "1–3 weeks — requires Meta Business Verification, dedicated phone number, and template approval."),
    ("Message Style & Length", "Rich formatting, long announcements, receipts, newsletters, and one-click unsubscribe links.", "Short, plain ASCII text strictly capped at 160 chars (no emojis) for single-part billing.", "Conversational rich media, buttons, and images, but strict pre-approved templates required."),
    ("Testing & Sandbox", "Very easy — ConsoleProvider locally + free Brevo tier for live sandbox emails.", "Easy locally via ConsoleProvider; live testing requires funded wallet & approved Sender ID.", "Complex — requires Meta test numbers and webhook setup."),
    ("Best Fit for Salutia", "Hotels (booking welcomes, loyalty offers, holiday cards) & fee-paying private school newsletters.", "Schools (resumption notices, PTA reminders, urgent alerts, seasonal greetings to all parents).", "Phase 2 add-on for two-way hotel concierge replies or VIP guest follow-ups."),
]
for r in comparison_rows:
    ws1.append(list(r))
for r in ws1.iter_rows(min_row=2, max_row=ws1.max_row):
    r[0].font = BOLD_FONT
    for c in r:
        c.alignment = WRAP
auto_fit(ws1, [24, 42, 45, 42])

# Tab 2: SMS Planning
ws2 = wb.create_sheet("SMS Planning")
ws2.append(["Planning Area", "Nigerian Telecom Reality", "What to Do in Salutia"])
style_headers(ws2, 1)

sms_planning_rows = [
    ("Cost per Message", "Nigerian aggregators (Termii, Africa's Talking) charge per 160-character SMS part, and DND routes cost slightly more than standard promotional routes.", "Keep greetings concise (under 160 chars) and quote schools/hotels using the SMS Cost Estimator tab before each term or holiday."),
    ("Sender ID & DND Rules", "MTN, Airtel, Glo, and 9mobile block generic bulk SMS on Do-Not-Disturb (DND) numbers unless sent via a registered Alphanumeric Sender ID on a DND/transactional route.", "Register each school/hotel Sender ID (max 11 chars, e.g., STANNESOTK) on Termii 5–7 days before launch and set TERMII_CHANNEL=dnd in .env."),
    ("Message Length & Encoding", "Plain GSM-7 text allows 160 chars (153/part if split). Adding even 1 emoji or curly quote switches encoding to UCS-2, cutting the limit to 70 chars (67/part) and multiplying cost.", "Use Salutia's built-in live character counter and analyze_sms() guardrail to warn staff whenever a draft exceeds 160 chars or contains non-GSM characters."),
    ("Consent & Opt-Out Compliance", "Nigeria Data Protection Act (NDPA) and NCC rules require documented opt-in consent and an easy way for recipients to opt out.", "Collect explicit consent on signup/CSV upload (saved with timestamps) and use the Contacts Opt-Out toggle whenever a parent replies STOP."),
]
for r in sms_planning_rows:
    ws2.append(list(r))
for r in ws2.iter_rows(min_row=2, max_row=ws2.max_row):
    r[0].font = BOLD_FONT
    for c in r:
        c.alignment = WRAP
auto_fit(ws2, [28, 52, 52])

# Tab 3: SMS Cost Estimator
ws3 = wb.create_sheet("SMS Cost Estimator")
ws3["A1"] = "Salutia Nigerian SMS Cost Estimator"
ws3["A1"].font = TITLE_FONT
ws3.append([])
ws3.append(["Input Parameter", "Value", "Notes"])
style_headers(ws3, 3)

inputs = [
    ("Number of Contacts", 500, "e.g., 500 parents for a secondary school in Otukpo"),
    ("Greetings per Year", 6, "e.g., 3 term resumptions + Christmas, Eid, Independence Day"),
    ("Message Length (characters)", 145, "Keep <= 160 plain GSM-7 characters for 1 SMS part"),
    ("Price per SMS Part (₦)", 5.50, "Typical Termii DND route rate in Naira (₦)"),
]
for label, val, note in inputs:
    ws3.append([label, val, note])

for r in range(4, 8):
    ws3[f"A{r}"].font = BOLD_FONT
    ws3[f"B{r}"].fill = INPUT_FILL
    ws3[f"B{r}"].font = BOLD_FONT
ws3["B4"].number_format = "#,##0"
ws3["B5"].number_format = "#,##0"
ws3["B6"].number_format = "#,##0"
ws3["B7"].number_format = "₦#,##0.00"

ws3.append([])
ws3.append(["Calculated Output", "Formula Result", "How It Works"])
style_headers(ws3, 9)

outputs = [
    ("SMS Parts per Message", "=IF(B6<=0,0,IF(B6<=160,1,ROUNDUP(B6/153,0)))", "1 part up to 160 chars; 153 chars per part when concatenated", "#,##0"),
    ("Cost per Single Recipient (₦)", "=B10*B7", "Parts per message × Price per SMS part", "₦#,##0.00"),
    ("Total Cost per Broadcast Send (₦)", "=B4*B11", "Number of contacts × Cost per single recipient", "₦#,##0.00"),
    ("Total Annual SMS Cost (₦)", "=B12*B5", "Cost per broadcast send × Greetings per year", "₦#,##0.00"),
]
for idx, (label, formula, desc, num_fmt) in enumerate(outputs, start=10):
    ws3.append([label, formula, desc])
    ws3[f"A{idx}"].font = BOLD_FONT
    ws3[f"B{idx}"].font = BOLD_FONT
    ws3[f"B{idx}"].fill = SUBHEADER_FILL
    ws3[f"B{idx}"].number_format = num_fmt
auto_fit(ws3, [34, 20, 52])

# Tab 4: Next Steps
ws4 = wb.create_sheet("Next Steps")
ws4.append(["Step", "Action Item", "Details & Goal", "Status"])
style_headers(ws4, 1)

steps = [
    ("Step 1", "Build Core & Test Mode", "Multi-tenant Flask app, consent-aware contacts, 160-char SMS guard, and ConsoleProvider.", "Done"),
    ("Step 2", "Add Compose, CSV Upload & Unsubscribe", "Batch sending with SendLog audit trail, Nigerian 080->+234 CSV importer, and one-click unsubscribe.", "Done"),
    ("Step 3", "Verify Free Email via Brevo", "Create a free Brevo account, verify sender email, and test live email delivery in .env.", "Not started"),
    ("Step 4", "Validate with 3–5 Local Contacts", "Speak with a local school administrator and hotel manager in Otukpo to confirm preferred channels and greeting templates.", "Not started"),
    ("Step 5", "Register Nigerian SMS Sender ID", "Complete Termii KYC and submit Alphanumeric Sender ID (allow 3–7 business days for approval).", "Not started"),
    ("Step 6", "Wire Live Termii DND SMS", "Add TERMII_API_KEY, TERMII_SENDER_ID, and TERMII_CHANNEL=dnd to .env.", "Not started"),
    ("Step 7", "Run 5-Contact Live Pilot", "Send a real test greeting to 5 consenting contacts and verify delivery across MTN/Airtel/Glo.", "Not started"),
    ("Step 8", "Onboard First Paying School or Hotel", "Use the SMS Cost Estimator tab to price an annual greeting package and import their contact CSV.", "Not started"),
]
for r in steps:
    ws4.append(list(r))

dv = DataValidation(type="list", formula1='"Not started,In progress,Done"', allow_blank=False)
ws4.add_data_validation(dv)
dv.add("D2:D9")

for r in ws4.iter_rows(min_row=2, max_row=9):
    r[0].font = BOLD_FONT
    r[1].font = BOLD_FONT
    for c in r:
        c.alignment = WRAP
auto_fit(ws4, [12, 36, 56, 18])

wb.save("salutia_channel_comparison.xlsx")
print("Created salutia_channel_comparison.xlsx successfully!")
