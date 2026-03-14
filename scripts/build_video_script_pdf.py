#!/usr/bin/env python3
"""Generate the 3-minute video script as a PDF (what to do + what to say)."""
import os
import sys

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
except ImportError:
    print("Install reportlab: pip install reportlab")
    sys.exit(1)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "StudentHelp_Video_Script_3min.pdf")


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="Title",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    )
    section_style = ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#6d28d9"),
    )
    do_style = ParagraphStyle(
        name="Do",
        parent=styles["Normal"],
        fontSize=10,
        leftIndent=0,
        spaceAfter=4,
        backColor=colors.HexColor("#f3effe"),
        borderPadding=6,
    )
    say_style = ParagraphStyle(
        name="Say",
        parent=styles["Normal"],
        fontSize=10,
        leftIndent=0,
        spaceAfter=8,
    )

    story = []

    story.append(Paragraph("StudentHelp — 3-Minute Demo Script", title_style))
    story.append(Paragraph(
        "What to do on the computer and what to say (~3 min). "
        "Before recording: run <b>venv/bin/python app.py</b>, open http://localhost:8080. "
        "Demo logins: nina@scu.edu / password, sarah@scu.edu / password.",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.2 * inch))

    sections = [
        ("[0:00–0:15] INTRODUCTION", "Show: Homepage or logo.", "Say: “Students need help but often don’t know who to ask. StudentHelp is a peer tutoring platform: you post requests, offer help, message, and schedule sessions in one place. It’s for students—whether you need help, want to help, or both.”"),
        ("[0:25–0:50] SIGN UP & ROLES", "Show: Register screen. Click through role selection (Requester / Helper / Both).", "Say: “Getting started is simple. You register with your name and email and choose your role: Requester if you mainly need help, Helper if you want to tutor, or Both if you do either. This helps the platform tailor what you see—for example, helpers see a way to browse and offer on requests.”"),
        ("[0:50–1:20] BROWSE REQUESTS & SEARCH/FILTER", "Show: Browse / Requests list. Use search box and filters (subject, urgency).", "Say: “On the Browse or requests page you see all open help requests. Each card shows the subject, a short description, and urgency—like high, medium, or low. You can search by keyword and filter by subject and urgency so you quickly find requests that match what you’re interested in or what you need help with.”"),
        ("[1:20–1:45] MY REQUESTS — CREATE & MANAGE", "Show: My Requests. Create a new request (subject, description, urgency). Show list and statuses (open / in progress / closed).", "Say: “If you need help, you go to My Requests. Here you create a new request: pick a subject, write a short description, and set the urgency. You can view all your requests and see their status—open, in progress, or closed. You can delete a request you no longer need or mark one as complete when you’re done.”"),
        ("[1:45–2:15] OFFER HELP & MESSAGES", "Show: From Browse, open a request → click Offer Help → go to Messages and show the new conversation.", "Say: “When you see a request you can help with, you click Offer Help and add a short message. That automatically starts a conversation between you and the requester. In Messages you see all your conversations and can chat back and forth. So offering help and messaging are tied together—no need to exchange contact info elsewhere.”"),
        ("[2:15–2:40] ACCEPT OFFER & SESSIONS", "Show: As requester, open a request that has offers → accept an offer → go to Sessions.", "Say: “When someone offers help, the requester can accept that offer. Accepting an offer creates a tutoring session—you’ll see it under Sessions. Sessions show as upcoming or past, so both sides know when they’re meeting. This keeps everything from ‘I need help’ to ‘we had a session’ in one product.”"),
        ("[2:40–2:55] PROFILE & WRAP-UP", "Show: Profile page (name, bio, role, session count).", "Say: “Under Profile you can edit your name, bio, and role, and see how many sessions you’ve had—useful for both requesters and helpers to keep track of their activity. So to recap: StudentHelp connects students who need help with students who want to help—through requests, offers, messages, and sessions—so peer tutoring is easy to find and manage.”"),
        ("[2:55–3:00] CLOSING", "Show: StudentHelp logo or homepage.", "Say: “Thanks for watching. Try it at the link below—and good luck with your classes.”"),
    ]

    for title, do, say in sections:
        story.append(Paragraph(title, section_style))
        story.append(Paragraph("<b>Do:</b> " + do, do_style))
        story.append(Paragraph("<b>Say:</b> " + say, say_style))

    doc.build(story)
    print("Wrote:", os.path.abspath(OUTPUT_PATH))


if __name__ == "__main__":
    build_pdf()
