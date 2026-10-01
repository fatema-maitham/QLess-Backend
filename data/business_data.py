# data/business_data.py
from datetime import time

from models.branch import BranchModel
from models.business import BusinessModel
from models.operating_hour import OperatingHourModel
from models.queue import QueueModel
from models.service import ServiceModel
from models.staff import StaffModel

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def make_hours(business, branch, open_at, close_at, closed_days=("friday",)):
    hours = []
    for day in DAYS:
        if day in closed_days:
            hours.append(OperatingHourModel(business=business, branch=branch, day_of_week=day, is_closed=True))
        else:
            hours.append(
                OperatingHourModel(
                    business=business, branch=branch, day_of_week=day, open_time=open_at, close_time=close_at
                )
            )
    return hours


def create_businesses(users, categories):
    owner = users["owner"]
    records = []

    # ---------- Approved business 1: a bank with two branches ----------
    bank = BusinessModel(
        owner=owner,
        category=categories["banking"],
        name="Pearl Bank",
        description="Personal and business banking",
        phone="17000001",
        email="info@pearlbank.test",
        approval_status="approved",
    )
    manama = BranchModel(business=bank, name="Manama Branch", address="Road 1, Manama", phone="17000011")
    riffa = BranchModel(business=bank, name="Riffa Branch", address="Road 2, Riffa", phone="17000012")

    accounts = ServiceModel(business=bank, branch=manama, name="Open an Account", duration_minutes=20)
    cards = ServiceModel(business=bank, branch=manama, name="Card Services", duration_minutes=10)
    riffa_teller = ServiceModel(business=bank, branch=riffa, name="Teller", duration_minutes=5)

    records += [bank, manama, riffa, accounts, cards, riffa_teller]
    records += make_hours(bank, manama, time(8, 0), time(14, 0))
    records += make_hours(bank, riffa, time(8, 0), time(14, 0))

    records += [
        QueueModel(
            business=bank, branch=manama, service=accounts, name="Accounts Queue",
            status="open", max_capacity=30, average_service_minutes=20, no_show_grace_minutes=5,
        ),
        QueueModel(
            business=bank, branch=manama, service=cards, name="Cards Queue",
            status="closed", max_capacity=20, average_service_minutes=10, no_show_grace_minutes=5,
        ),
        QueueModel(
            business=bank, branch=riffa, service=riffa_teller, name="Teller Queue",
            status="open", average_service_minutes=5, no_show_grace_minutes=3,
        ),
    ]

    # The seeded staff user works at the Manama branch
    records.append(StaffModel(user=users["staff"], business=bank, branch=manama, position="Teller"))

    # ---------- Approved business 2: a clinic ----------
    clinic = BusinessModel(
        owner=owner,
        category=categories["healthcare"],
        name="Dilmun Clinic",
        description="Family medicine and check-ups",
        phone="17000002",
        email="hello@dilmunclinic.test",
        approval_status="approved",
    )
    seef = BranchModel(business=clinic, name="Seef Branch", address="Road 3, Seef", phone="17000021")
    checkup = ServiceModel(business=clinic, branch=seef, name="General Check-up", duration_minutes=15)

    records += [clinic, seef, checkup]
    records += make_hours(clinic, seef, time(9, 0), time(21, 0), closed_days=())
    records.append(
        QueueModel(
            business=clinic, branch=seef, service=checkup, name="Walk-in Queue",
            status="open", max_capacity=25, average_service_minutes=15, no_show_grace_minutes=10,
        )
    )

    # ---------- Pending business: must NOT appear on the public browse page ----------
    records.append(
        BusinessModel(
            owner=owner,
            category=categories["salons"],
            name="Seef Salon",
            description="Hair and beauty",
            approval_status="pending",
        )
    )

    return records