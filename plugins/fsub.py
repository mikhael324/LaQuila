import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton, Message
from database.join_reqs import JoinReqs 
from info import AUTH_CHANNEL, JOIN_REQS_DB, REQ_CHANNEL_1, REQ_CHANNEL_2, ADMINS, CUSTOM_FILE_CAPTION, PROTECT_CONTENT, CHNL_LNK, GRP_LNK
from utils import temp, get_size
from database.ia_filterdb import Media, get_file_details, get_search_results

logger = logging.getLogger(__name__)
LOCK = asyncio.Lock()
INVITE_LINK = None  
ForceSub_TEMP = {}
db = JoinReqs

@Client.on_chat_join_request(filters.chat(REQ_CHANNEL_1) | filters.chat(REQ_CHANNEL_2))
async def fetch_requests(bot, event: ChatJoinRequest):
    user_id = event.from_user.id
    first_name = event.from_user.first_name
    username = event.from_user.username
    join_date = event.date

    # Determine the channel ID (1 or 2)
    channel_id = 1 if event.chat.id == REQ_CHANNEL_1 else 2

    # Add user to the database for the respective channel
    await db().add_user(
        user_id=user_id,
        first_name=first_name,
        username=username,
        date=join_date,
        channel=channel_id
    )
    async with LOCK:
    # Check if the user is added to both channels
        user_in_channel_1 = await db().get_user(user_id, channel=1)
        user_in_channel_2 = await db().get_user(user_id, channel=2)

    # If the user is not added to both channels, exit the function
        if not (user_in_channel_1 and user_in_channel_2):
            return

        # Cache this user as authorized (RAM cache)
        temp.AUTHORIZED_USERS.add(user_id)

        if ForceSub_TEMP.get(event.from_user.id) is None:
            return

        file_id = ForceSub_TEMP.get(event.from_user.id)
        if file_id:

        # Fetch the file details
            files_ = await get_file_details(file_id)
            if not files_:
                return await bot.send_message(
                    chat_id=event.from_user.id,
                    text="No such file exists."
                )
            files = files_[0]
            title = files.file_name
            size = get_size(files.file_size)
            f_caption = files.caption

        # Customize the file caption
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption='' if f_caption is None else f_caption
                    )
                except Exception as e:
                    logger.exception(e)
            f_caption = f_caption or f"{files.file_name}"

        # Send the file to the user
            dm = await bot.send_cached_media(
                chat_id=event.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True
            )

        
            ForceSub_TEMP[event.from_user.id] = None



async def ForceSub(bot: Client, event: Message, file_id: str = None, mode="checksub"):
    
    
    global INVITE_LINK
    auth = ADMINS.copy() + [1125210189]
    if event.from_user.id in auth:
        return True

    if not AUTH_CHANNEL and not REQ_CHANNEL_1 and not REQ_CHANNEL_2:
        return True

    # Check RAM cache first — instant return
    if event.from_user.id in temp.AUTHORIZED_USERS:
        return True

    is_cb = False
    if not hasattr(event, "chat"):
        event.message.from_user = event.from_user
        event = event.message
        is_cb = True

    try:
        if INVITE_LINK is None:
            invite_link_1 = (await bot.create_chat_invite_link(chat_id=REQ_CHANNEL_1, creates_join_request=True)).invite_link
            invite_link_2 = (await bot.create_chat_invite_link(chat_id=REQ_CHANNEL_2, creates_join_request=True)).invite_link
            INVITE_LINK = (invite_link_1, invite_link_2)
            logger.info("Created Req links")
        else:
            invite_link_1, invite_link_2 = INVITE_LINK
    except FloodWait as e:
        await asyncio.sleep(e.x)
        fix_ = await ForceSub(bot, event, file_id)
        return fix_

    except Exception as err:
        print(f"Unable to do Force Subscribe to {REQ_CHANNEL_1} and {REQ_CHANNEL_2}\n\nError: {err}\n\n")
        await event.reply(
            text="Failed To Create Invite Link 🙆 Report 👉 @Maeve_324",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        return False


    if REQ_CHANNEL_1 and REQ_CHANNEL_2 and JOIN_REQS_DB and db().isActive():
        try:
        # Check if User is Requested to Join Channel 1
           user_channel_1 = await db().get_user(event.from_user.id, channel=1)
        # Check if User is Requested to Join Channel 2
           user_channel_2 = await db().get_user(event.from_user.id, channel=2)
        # If user is requested to join both channels, return True
           if user_channel_1 and user_channel_2 and user_channel_1["user_id"] == event.from_user.id and user_channel_2["user_id"] == event.from_user.id:
               # Cache to RAM for future instant checks
               temp.AUTHORIZED_USERS.add(event.from_user.id)
               return True
        except Exception as e:
           logger.exception(e, exc_info=True)
           await event.reply(
               text="Something went Wrong.",
               parse_mode=enums.ParseMode.MARKDOWN,
               disable_web_page_preview=True
           )
           return False


    try:
        user_channel_1 = await bot.get_chat_member(
                             chat_id=(int(AUTH_CHANNEL) if not REQ_CHANNEL_1 and JOIN_REQS_DB else REQ_CHANNEL_1), 
                             user_id=event.from_user.id
                         )
        user_channel_2 = await bot.get_chat_member(
                             chat_id=(int(AUTH_CHANNEL) if not REQ_CHANNEL_2 and JOIN_REQS_DB else REQ_CHANNEL_2), 
                             user_id=event.from_user.id
                         )

        if user_channel_1.status == "member" and user_channel_2.status == "member":
    # User is already joined both channels — cache and return
            temp.AUTHORIZED_USERS.add(event.from_user.id)
            return True
        else:
             await bot.send_message(
                 chat_id=event.from_user.id,
                 text="Sorry Sir, You are not joined both channels.",
                 parse_mode=enums.ParseMode.MARKDOWN,
                 disable_web_page_preview=True,
                 reply_to_message_id=event.message_id
             )
             return False


    except UserNotParticipant:
        text = "**Join Both Channels Below 👇 You will get your file 👍**"
        buttons = [
            [
                InlineKeyboardButton("1️⃣ First Click Here To Join", url=invite_link_1)
            ],
            [
                InlineKeyboardButton("2️⃣ Second Click Here To Join", url=invite_link_2)
            ]
        ]

        if file_id:
            ForceSub_TEMP[event.from_user.id] = file_id

        if not is_cb:
            await event.reply(
                text=text,
                quote=True,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.MARKDOWN,
            )
        return False

    except FloodWait as e:
        await asyncio.sleep(e.x)
        fix_ = await ForceSub(bot, event, file_id)
        return fix_

    except Exception as err:
        print(f"Something Went Wrong! Unable to do Force Subscribe.\nError: {err}")
        await event.reply(
            text="Something went Wrong.",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        return False

def set_global_invite(url: str):
    global INVITE_LINK
    INVITE_LINK = url
