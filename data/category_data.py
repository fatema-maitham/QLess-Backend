# data/category_data.py
from models.category import CategoryModel


def create_categories():
    return {
        "banking": CategoryModel(name="Banking", description="Banks and money exchange"),
        "healthcare": CategoryModel(name="Healthcare", description="Clinics, hospitals and pharmacies"),
        "government": CategoryModel(name="Government", description="Public services and ministries"),
        "telecom": CategoryModel(name="Telecom", description="Mobile and internet providers"),
        "restaurants": CategoryModel(name="Restaurants", description="Cafes and restaurants"),
        "salons": CategoryModel(name="Salons", description="Barbers, salons and spas"),
    }