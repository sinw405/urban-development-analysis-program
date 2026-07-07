from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LawArticleVersion

VERSION_STATUS_CURRENT = "current"
VERSION_STATUS_PREVIOUS = "previous"
VERSION_STATUS_SCHEDULED = "scheduled"
VERSION_STATUS_UNKNOWN_EFFECTIVE_DATE = "unknown_effective_date"


@dataclass(frozen=True)
class VersionWithTemporalStatus:
    version: LawArticleVersion
    temporal_status: str


def classify_versions_as_of(
    versions: list[LawArticleVersion],
    as_of: date | None,
) -> list[VersionWithTemporalStatus]:
    if as_of is None:
        return [
            VersionWithTemporalStatus(
                version=version,
                temporal_status=VERSION_STATUS_UNKNOWN_EFFECTIVE_DATE
                if version.effective_date is None
                else VERSION_STATUS_PREVIOUS,
            )
            for version in versions
        ]

    current_version = _select_current_version(versions=versions, as_of=as_of)
    classified: list[VersionWithTemporalStatus] = []
    for version in versions:
        if version.effective_date is None:
            status = VERSION_STATUS_UNKNOWN_EFFECTIVE_DATE
        elif current_version is not None and version.id == current_version.id:
            status = VERSION_STATUS_CURRENT
        elif version.effective_date > as_of:
            status = VERSION_STATUS_SCHEDULED
        else:
            status = VERSION_STATUS_PREVIOUS
        classified.append(VersionWithTemporalStatus(version=version, temporal_status=status))
    return classified


def get_article_versions(
    db: Session,
    article_id: int,
    as_of: date | None = None,
) -> list[VersionWithTemporalStatus]:
    versions = list(
        db.scalars(
            select(LawArticleVersion)
            .where(LawArticleVersion.law_article_id == article_id)
            .order_by(LawArticleVersion.effective_date.asc().nullsfirst(), LawArticleVersion.id.asc())
        ).all()
    )
    return classify_versions_as_of(versions=versions, as_of=as_of)


def get_current_article_version(
    db: Session,
    article_id: int,
    as_of: date,
) -> LawArticleVersion | None:
    versions = [item.version for item in get_article_versions(db=db, article_id=article_id, as_of=as_of)]
    return _select_current_version(versions=versions, as_of=as_of)


def _select_current_version(
    versions: list[LawArticleVersion],
    as_of: date,
) -> LawArticleVersion | None:
    effective_versions = [
        version for version in versions if version.effective_date is not None and version.effective_date <= as_of
    ]
    if not effective_versions:
        return None
    return max(effective_versions, key=lambda version: (version.effective_date, version.id))
