from fastapi import APIRouter

from . import admin, auth, author_notes, gm, llm_config, novels, updates, writer

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(novels.router)
api_router.include_router(writer.router)
api_router.include_router(admin.router)
api_router.include_router(updates.router)
api_router.include_router(llm_config.router)
api_router.include_router(gm.router)
# 作者备忘录和角色状态
api_router.include_router(author_notes.router)
api_router.include_router(author_notes.states_router)
api_router.include_router(author_notes.context_router)
api_router.include_router(author_notes.template_router)
