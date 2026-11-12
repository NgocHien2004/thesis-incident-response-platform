from typing import Iterable, List

def chunks(seq: Iterable, size: int = 500) -> List[list]:
    seq = list(seq)
    return [seq[i:i + size] for i in range(0, len(seq), size)]

def page_response(items: list, total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size else 0}

def apply_page(q, order_by: list, page: int, page_size: int):
    # SQL Server không cho ORDER BY trong truy vấn con của count(), nên đếm trước rồi mới sắp xếp
    total = q.count()
    rows = q.order_by(*order_by).offset((page - 1) * page_size).limit(page_size).all()
    return rows, total
