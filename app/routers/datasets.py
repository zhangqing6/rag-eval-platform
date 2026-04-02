import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Dataset, TestCase
from app.schemas import DatasetCreate, DatasetRead, TestCaseBulkUpload, TestCaseItem

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetRead)
def create_dataset(body: DatasetCreate, session: Session = Depends(get_session)) -> Dataset:
    ds = Dataset(name=body.name, description=body.description)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


@router.get("", response_model=list[DatasetRead])
def list_datasets(session: Session = Depends(get_session)) -> list[Dataset]:
    return list(session.exec(select(Dataset).order_by(Dataset.id.desc())).all())


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: int, session: Session = Depends(get_session)) -> Dataset:
    ds = session.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@router.post("/{dataset_id}/cases", response_model=dict)
def upload_cases(
    dataset_id: int,
    body: TestCaseBulkUpload,
    session: Session = Depends(get_session),
) -> dict:
    ds = session.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    n = 0
    for item in body.cases:
        tc = TestCase(
            dataset_id=dataset_id,
            question=item.question,
            reference_answer=item.reference_answer,
            tags=json.dumps(item.tags, ensure_ascii=False),
            must_contain=json.dumps(item.must_contain, ensure_ascii=False),
            extra=json.dumps(item.extra, ensure_ascii=False),
        )
        session.add(tc)
        n += 1
    session.commit()
    return {"added": n}


@router.get("/{dataset_id}/cases", response_model=list[dict])
def list_cases(dataset_id: int, session: Session = Depends(get_session)) -> list[dict]:
    ds = session.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    cases = session.exec(select(TestCase).where(TestCase.dataset_id == dataset_id).order_by(TestCase.id)).all()
    out: list[dict] = []
    for c in cases:
        out.append(
            {
                "id": c.id,
                "question": c.question,
                "reference_answer": c.reference_answer,
                "tags": json.loads(c.tags or "[]"),
                "must_contain": json.loads(c.must_contain or "[]"),
            }
        )
    return out
