"""Explicit development samples. Run: python -m app.public_seed --demo."""

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_engine
from app.public_models import Branch, Program, PublicEvent

BRANCHES = [
    ("karachi", "Karachi", "کراچی", "Clifton", "کلفٹن"),
    ("lahore", "Lahore", "لاہور", "Gulberg", "گلبرگ"),
    ("islamabad", "Islamabad", "اسلام آباد", "F-7", "ایف سیون"),
]
PROGRAMS = [
    (
        "learning",
        "Learning together",
        "مل کر سیکھیں",
        (
            "Help run reading circles, practise everyday digital skills and make "
            "learning more approachable. Volunteers plan small sessions with a local "
            "coordinator."
        ),
        (
            "مطالعے کے حلقوں اور روزمرہ ڈیجیٹل مہارتوں کی نشستوں میں مدد کریں۔ رضاکار "
            "مقامی رابطہ کار کے ساتھ چھوٹی نشستیں ترتیب دیتے ہیں۔"
        ),
        "Readers, tutors and patient listeners",
        "قارئین، اساتذہ اور توجہ سے سننے والے",
    ),
    (
        "neighbourhood",
        "Neighbourhood care",
        "محلے کی دیکھ بھال",
        (
            "Work with a local team on practical community activities, from shared-space "
            "cleanups to organising useful supplies. Each activity starts with a clear "
            "brief."
        ),
        (
            "مقامی ٹیم کے ساتھ مشترکہ جگہوں کی صفائی اور ضروری سامان کی ترتیب جیسی "
            "سرگرمیوں میں حصہ لیں۔ ہر سرگرمی واضح ہدایات سے شروع ہوتی ہے۔"
        ),
        "People who enjoy practical, team-based work",
        "عملی اور اجتماعی کام پسند کرنے والے افراد",
    ),
    (
        "skills",
        "Skills for good",
        "ہنر سے خدمت",
        (
            "Share design, administration or communication skills with branch teams. "
            "Take on a clearly scoped task that fits the time you can offer."
        ),
        (
            "شاخوں کی ٹیموں کے ساتھ ڈیزائن، انتظام یا رابطے کی مہارت بانٹیں۔ اپنے دستیاب "
            "وقت کے مطابق واضح کام منتخب کریں۔"
        ),
        "People sharing professional or everyday skills",
        "پیشہ ورانہ یا روزمرہ مہارت بانٹنے والے افراد",
    ),
]
EVENTS = [
    (
        "meet-team",
        "Meet your local team",
        "اپنی مقامی ٹیم سے ملیں",
        0,
        7,
        (
            "An introductory conversation about local volunteering. Meet a coordinator, "
            "ask questions and explore where your interests could fit."
        ),
        (
            "مقامی رضاکارانہ کام کے بارے میں تعارفی گفتگو۔ رابطہ کار سے ملیں، سوال "
            "پوچھیں اور اپنی دلچسپی کے مواقع جانیں۔"
        ),
    ),
    (
        "reading-circle",
        "Community reading circle",
        "اجتماعی مطالعے کی نشست",
        1,
        12,
        (
            "An informal reading and discussion session. Bring a short passage you "
            "enjoy, or simply come ready to listen. Materials are provided in this "
            "sample activity."
        ),
        (
            "مطالعے اور گفتگو کی غیر رسمی نشست۔ اپنی پسند کی مختصر تحریر لائیں یا سننے "
            "کے لیے آئیں۔ یہ ایک نمونہ سرگرمی ہے۔"
        ),
    ),
    (
        "digital-basics",
        "Everyday digital skills",
        "روزمرہ ڈیجیٹل مہارتیں",
        2,
        18,
        (
            "A beginner-friendly session on organising files, writing clear emails and "
            "finding reliable information online. No previous experience is needed."
        ),
        (
            "فائلیں ترتیب دینے، واضح ای میل لکھنے اور آن لائن قابل اعتماد معلومات تلاش "
            "کرنے کی ابتدائی نشست۔ پہلے سے تجربہ ضروری نہیں۔"
        ),
    ),
    (
        "neighbourhood-day",
        "Neighbourhood action day",
        "محلے کی خدمت کا دن",
        0,
        24,
        (
            "Plan a small community project together. The session covers roles, supplies "
            "and a simple checklist for working safely as a team."
        ),
        (
            "مل کر ایک چھوٹے اجتماعی منصوبے کی تیاری کریں۔ نشست میں ذمہ داریوں، سامان "
            "اور محفوظ اجتماعی کام کی بنیادی ہدایات پر بات ہوگی۔"
        ),
    ),
    (
        "skills-exchange",
        "A skills exchange",
        "ہنر کا تبادلہ",
        1,
        31,
        (
            "Share a useful skill with other volunteers in a relaxed workshop. Short "
            "demonstrations and conversation help everyone find something new to try."
        ),
        (
            "ایک دوستانہ ورکشاپ میں دوسرے رضاکاروں کے ساتھ مفید ہنر بانٹیں۔ مختصر مظاہرے "
            "اور گفتگو نئی چیز سیکھنے میں مدد دیتے ہیں۔"
        ),
    ),
    (
        "welcome-session",
        "Volunteer welcome session",
        "رضاکاروں کی استقبالیہ نشست",
        2,
        38,
        (
            "Learn how branch teams organise their work, what support volunteers receive "
            "and how to make your first contribution."
        ),
        (
            "جانیں کہ شاخوں کی ٹیمیں کام کیسے منظم کرتی ہیں، رضاکاروں کو کیا مدد ملتی ہے "
            "اور پہلا قدم کیسے اٹھایا جائے۔"
        ),
    ),
]


def seed_public_content(session: Session) -> int:
    if get_settings().environment == "production":
        raise ValueError("Demo seeding is forbidden in production.")
    created = 0

    def add(model, slug, **values):
        nonlocal created
        row = session.scalar(select(model).where(model.slug == slug))
        if row is None:
            row = model(slug=slug, is_demo=True, is_published=True, **values)
            session.add(row)
            session.flush()
            created += 1
        return row

    branches = []
    for slug, city, city_ur, area, area_ur in BRANCHES:
        branches.append(
            add(
                Branch,
                slug + "-demo",
                name=f"{city} branch",
                name_ur=f"{city_ur} شاخ",
                city=city,
                city_ur=city_ur,
                address=f"{area}, {city} — illustrative location only",
                address_ur=f"{area_ur}، {city_ur} — صرف مثالی مقام",
                hours="Monday–Friday, 9:00 am–5:00 pm (PKT)",
                hours_ur="پیر تا جمعہ، صبح ۹ تا شام ۵ (پاکستانی وقت)",
                description=(
                    f"A sample local office connecting volunteers and community activities in "
                    f"{city}. Contact the team through the website to explore ways to contribute."
                ),
                description_ur=(
                    f"{city_ur} میں رضاکاروں اور اجتماعی سرگرمیوں کو جوڑنے والا نمونہ دفتر۔ خدمت "
                    f"کے مواقع جاننے کے لیے ویب سائٹ سے رابطہ کریں۔"
                ),
            )
        )
    for slug, title, title_ur, description, description_ur, audience, audience_ur in PROGRAMS:
        add(
            Program,
            slug + "-demo",
            title=title,
            title_ur=title_ur,
            description=description,
            description_ur=description_ur,
            audience=audience,
            audience_ur=audience_ur,
        )
    start = datetime.now(UTC).replace(hour=5, minute=0, second=0, microsecond=0)
    for slug, title, title_ur, branch, days, description, description_ur in EVENTS:
        when = start + timedelta(days=days)
        add(
            PublicEvent,
            slug + "-demo",
            title=title,
            title_ur=title_ur,
            description=description,
            description_ur=description_ur,
            branch_id=branches[branch].id,
            starts_at=when,
            ends_at=when + timedelta(hours=2),
        )
    return created


def main():
    parser = argparse.ArgumentParser(description="Seed fictional public content in development.")
    parser.add_argument("--demo", action="store_true", required=True)
    parser.parse_args()
    with Session(get_engine()) as session, session.begin():
        count = seed_public_content(session)
    print(f"Created {count} demo public records; existing content preserved.")


if __name__ == "__main__":
    main()
