import logging
from typing import Any, Optional, Union

from ntgcalls import ConnectionError
from ntgcalls import FileError
from ntgcalls import InvalidParams
from ntgcalls import TelegramServerError

from ...exceptions import AlreadyJoinedError
from ...exceptions import FileNotFoundError
from ...exceptions import NoActiveGroupCall
from ...exceptions import UnMuteNeeded
from ...mtproto import BridgedClient
from ...mtproto_required import mtproto_required
from ...scaffold import Scaffold
from ...statictypes import statictypes
from ...to_async import ToAsync
from ...types.raw.stream import Stream
from ..utilities.stream_params import StreamParams

py_logger = logging.getLogger('pytgcalls')


class JoinGroupCall(Scaffold):
    @statictypes
    @mtproto_required
    async def join_group_call(
        self,
        chat_id: Union[int, str],
        stream: Optional[Stream] = None,
        invite_hash: Optional[str] = None,
        join_as: Any = None,
        auto_start: bool = True,
    ):
        if join_as is None:
            join_as = self._cache_local_peer

        chat_id = await self._resolve_chat_id(chat_id)
        self._cache_user_peer.put(
             chat_id, join_as
        )
        chat_call = await self._app.get_full_chat(
              chat_id
        )
        if chat_call is None:
            if auto_start:
                await self._app.create_group_call(
                    chat_id
                )
            else:
                raise NoActiveGroupCall()

        media_description = await StreamParams.get_stream_params(
              stream
        )
        try:
            call_params: str = await ToAsync(
                   self._binding.create_call, 
                   chat_id, 
                   media_description
            )
            try:
                result_params = await self._app.join_group_call(
                    chat_id, 
                    call_params, 
                    invite_hash, 
                    media_description.video is None,
                    self._cache_user_peer.get(chat_id)
                )
                await ToAsync(
                    self._binding.connect, 
                    chat_id, 
                    result_params
                )
                await self._check_unmute_needed(
                    chat_id
                )
            except (
                TelegramServerError, 
                FileError, 
                ConnectionError, 
                InvalidParams
            ) as e:
                raise RuntimeError(f"Error joining group call: {e}")
        except (
            FileNotFoundError, 
            AlreadyJoinedError, 
            UnMuteNeeded
        ) as e:
            raise RuntimeError(str(e))

    async def _check_unmute_needed(
        self, 
        chat_id: Union[int, str]
    ):
        participants = await self._app.get_group_call_participants(
            chat_id
        )
        for participant in participants:
            if participant.user_id == BridgedClient.chat_id(self._cache_local_peer) and participant.muted_by_admin:
                self._need_unmute.add(
                    chat_id
                )
