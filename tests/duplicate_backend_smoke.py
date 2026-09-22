from pathlib import Path

from core.models import Photo
from features.duplicate import service as duplicate


def make(name, quality, phash=1):
    photo = Photo(Path(name))
    photo.sample_id = name
    photo.phash = phash
    photo.face_quality = quality
    photo.brisque = 10.0
    photo.blur = 100.0
    return photo


def main():
    a = make("a.jpg", 0.9, 123)
    b = make("b.jpg", 0.8, 123)
    c = make("c.jpg", 0.7, 123)
    c.duplicate_ignore = True
    records = [a, b, c]

    duplicate.group_duplicates(records, threshold=0, adjacent=0)
    assert a.duplicate_group
    assert a.duplicate_group == b.duplicate_group
    assert c.duplicate_group == 0

    gid = a.duplicate_group
    assert duplicate.group_ids(records) == (gid,)
    assert duplicate.group_members(records, gid) == [a, b]
    assert duplicate.group_members(records, duplicate.IGNORED_GROUP_ID) == [c]
    assert not duplicate.group_reviewed(records, gid)

    assert duplicate.keep_best(records, gid) == 2
    assert a.manual_status == "推荐"
    assert b.manual_status == "淘汰"
    assert duplicate.group_reviewed(records, gid)

    assert duplicate.restore_auto(records, gid) == 2
    assert a.manual_status is None and b.manual_status is None
    assert not a.duplicate_reviewed and not b.duplicate_reviewed

    assert duplicate.apply_checked(records, gid, {"b.jpg"}) == 2
    assert a.manual_status == "淘汰"
    assert b.manual_status == "推荐"

    assert duplicate.keep_all(records, gid) == 2
    assert a.manual_status == "推荐"
    assert b.manual_status == "推荐"

    duplicate.restore_auto(records, gid)
    assert duplicate.apply_all_groups(records, {"a.jpg"}) == 2
    assert a.manual_status == "推荐"
    assert b.manual_status == "淘汰"

    assert duplicate.set_ignored(records, {"b.jpg"}, True) == 1
    assert b.duplicate_ignore
    duplicate.group_duplicates(records, threshold=0, adjacent=0)
    assert a.duplicate_group == 0
    assert b.duplicate_group == 0

    assert duplicate.set_ignored(records, {"b.jpg"}, False) == 1
    duplicate.group_duplicates(records, threshold=0, adjacent=0)
    assert a.duplicate_group and a.duplicate_group == b.duplicate_group

    print("Duplicate backend smoke: PASS")


if __name__ == "__main__":
    main()
