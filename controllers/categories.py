# controllers/categories.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies.roles import require_admin
from models.category import CategoryModel
from models.user import UserModel
from serializers.category import CategoryCreateSchema, CategorySchema, CategoryUpdateSchema

router = APIRouter(prefix="/categories", tags=["Categories"])


def find_category(db: Session, category_id: int) -> CategoryModel:
    category = db.query(CategoryModel).filter(CategoryModel.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def name_taken(db: Session, name: str, exclude_id: int | None = None) -> bool:
    query = db.query(CategoryModel).filter(func.lower(CategoryModel.name) == name.lower())
    if exclude_id is not None:
        query = query.filter(CategoryModel.id != exclude_id)
    return query.first() is not None


@router.get("", response_model=list[CategorySchema])
def get_categories(db: Session = Depends(get_db)):
    return db.query(CategoryModel).order_by(CategoryModel.name).all()


@router.post("", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreateSchema,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    name = data.name.strip()
    if name_taken(db, name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A category with this name already exists")

    category = CategoryModel(name=name, description=data.description, image=data.image)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategorySchema)
def update_category(
    category_id: int,
    data: CategoryUpdateSchema,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    category = find_category(db, category_id)
    updates = data.model_dump(exclude_unset=True)

    if "name" in updates:
        updates["name"] = updates["name"].strip()
        if name_taken(db, updates["name"], exclude_id=category.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A category with this name already exists")

    for field, value in updates.items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    category = find_category(db, category_id)
    # Businesses in this category keep existing; their category_id becomes null
    db.delete(category)
    db.commit()
    return {"message": "Category deleted"}