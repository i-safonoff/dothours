import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.post import Comment, Post, PostLike
from app.models.user import User
from app.schemas.post import CommentCreate, CommentOut, PostCreate, PostOut
from app.schemas.user import UserPublic

router = APIRouter(tags=["posts"])


def _get_post_or_404(db: Session, post_id: uuid.UUID) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def _to_post_out(db: Session, post: Post, current_user_id: uuid.UUID) -> PostOut:
    author = db.get(User, post.author_id)
    liked = db.scalar(select(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == current_user_id))
    return PostOut(
        id=post.id,
        author=UserPublic.model_validate(author),
        text=post.text,
        created_at=post.created_at,
        likes_count=post.likes_count,
        comments_count=post.comments_count,
        liked_by_me=liked is not None,
    )


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostOut:
    post = Post(author_id=current_user.id, text=payload.text)
    db.add(post)
    db.commit()
    db.refresh(post)
    return _to_post_out(db, post, current_user.id)


@router.get("/posts", response_model=list[PostOut])
def list_posts(
    author_id: uuid.UUID | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PostOut]:
    stmt = select(Post)
    if author_id is not None:
        stmt = stmt.where(Post.author_id == author_id)
    stmt = stmt.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    posts = db.scalars(stmt).all()
    return [_to_post_out(db, p, current_user.id) for p in posts]


@router.get("/posts/{post_id}", response_model=PostOut)
def get_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostOut:
    post = _get_post_or_404(db, post_id)
    return _to_post_out(db, post, current_user.id)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    post = _get_post_or_404(db, post_id)
    if post.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your post")
    db.delete(post)
    db.commit()


@router.post("/posts/{post_id}/like", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def like_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostOut:
    post = _get_post_or_404(db, post_id)
    existing = db.scalar(select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == current_user.id))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already liked")

    db.add(PostLike(post_id=post_id, user_id=current_user.id))
    post.likes_count += 1
    db.commit()
    db.refresh(post)
    return _to_post_out(db, post, current_user.id)


@router.delete("/posts/{post_id}/like", response_model=PostOut)
def unlike_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostOut:
    post = _get_post_or_404(db, post_id)
    existing = db.scalar(select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == current_user.id))
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not liked yet")

    db.delete(existing)
    post.likes_count = max(0, post.likes_count - 1)
    db.commit()
    db.refresh(post)
    return _to_post_out(db, post, current_user.id)


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
def list_comments(
    post_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    _get_post_or_404(db, post_id)
    comments = db.scalars(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at).limit(limit).offset(offset)
    ).all()
    authors = {a.id: a for a in db.scalars(select(User).where(User.id.in_([c.author_id for c in comments])))}
    return [
        CommentOut(
            id=c.id,
            post_id=c.post_id,
            author=UserPublic.model_validate(authors[c.author_id]),
            text=c.text,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: uuid.UUID,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentOut:
    post = _get_post_or_404(db, post_id)
    comment = Comment(post_id=post_id, author_id=current_user.id, text=payload.text)
    db.add(comment)
    post.comments_count += 1
    db.commit()
    db.refresh(comment)
    return CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author=UserPublic.model_validate(current_user),
        text=comment.text,
        created_at=comment.created_at,
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your comment")

    post = db.get(Post, comment.post_id)
    db.delete(comment)
    if post is not None:
        post.comments_count = max(0, post.comments_count - 1)
    db.commit()
