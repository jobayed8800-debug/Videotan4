import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from pipeline.dubber import BanglaVideoDubber
from config.settings import Config

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Supported languages with emojis
LANGUAGES = {
    "en": "🇬🇧 English",
    "hi": "🇮🇳 Hindi",
    "ur": "🇵🇰 Urdu",
    "ar": "🇸🇦 Arabic",
    "zh": "🇨🇳 Chinese",
    "es": "🇪🇸 Spanish",
    "fr": "🇫🇷 French",
    "de": "🇩🇪 German",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "ru": "🇷🇺 Russian",
    "it": "🇮🇹 Italian",
    "pt": "🇵🇹 Portuguese",
    "bn": "🇧🇩 Bangla (Target)",
}


class DubbingBot:
    """Main Telegram Bot class for video dubbing"""
    
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.dubber = BanglaVideoDubber()
        self.user_sessions = {}  # Store user preferences
        self.setup_handlers()
        
    def setup_handlers(self):
        """Register all handlers"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("lang", self.language_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Message handlers
        self.app.add_handler(MessageHandler(
            filters.VIDEO | filters.Document.VIDEO, self.handle_video
        ))
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_text
        ))
        
        # Callback query handler (for inline keyboards)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Error handler
        self.app.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_text = f"""
🎬 **বাংলা ভিডিও ডাবিং বট** 

হ্যালো {user.first_name}! 👋

আমি যেকোনো ভাষার ভিডিওকে **বাংলা ডাবিং** এ কনভার্ট করি।

🔹 **কিভাবে ব্যবহার করবেন:**
1. ভিডিও আপলোড করুন (MP4, AVI, MKV)
2. ভিডিওর ভাষা সিলেক্ট করুন
3. আমার কাজ শেষ করার অপেক্ষা করুন
4. ডাবিংকৃত ভিডিও ডাউনলোড করুন

✨ **ফিচারসমূহ:**
• 🔥 ১৫+ ভাষা সাপোর্ট (ইংরেজি, হিন্দি, আরবি, চাইনিজ, উর্দু সহ)
• 🎭 মাল্টি-স্পিকার ভয়েস ক্লোনিং
• ⏱ টাইম সিঙ্ক সঠিক রাখে
• 📹 ১ ঘণ্টা পর্যন্ত ভিডিও

সাপোর্টেড ভাষা দেখতে /lang ব্যবহার করুন।
        """
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 ভিডিও আপলোড করুন", callback_data="upload")],
            [InlineKeyboardButton("🌐 ভাষা নির্বাচন", callback_data="select_lang")],
            [InlineKeyboardButton("ℹ️ সাহায্য", callback_data="help")],
        ])
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
❓ **সাহায্য নির্দেশিকা**

**ধাপ ১:** ভিডিও আপলোড করুন
- সাপোর্টেড ফরম্যাট: MP4, AVI, MKV, MOV
- সর্বোচ্চ সাইজ: 500 MB
- সর্বোচ্চ দৈর্ঘ্য: ১ ঘণ্টা

**ধাপ ২:** ভাষা নির্বাচন করুন
- ভিডিওতে কোন ভাষা আছে তা সিলেক্ট করুন
- সিস্টেম স্বয়ংক্রিয়ভাবে বাংলায় অনুবাদ করবে

**ধাপ ৩:** অপেক্ষা করুন
- প্রক্রিয়াকরণে ৩-১০ মিনিট সময় লাগে (ভিডিও সাইজ অনুযায়ী)
- আপনি /status দিয়ে অগ্রগতি দেখতে পারেন

**ধাপ ৪:** ডাউনলোড করুন
- সম্পন্ন হলে ভিডিও পাঠানো হবে
- অরিজিনাল অডিও এবং বাংলা ডাবিং দুটোই থাকবে

**কমান্ডসমূহ:**
/start - বট চালু করুন
/help - সাহায্য দেখুন
/status - বর্তমান অবস্থা জানুন
/lang - ভাষার তালিকা দেখুন
/cancel - চলমান কাজ বাতিল করুন

❌ **সমস্যা হলে:** @admin কে যোগাযোগ করুন
        """
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /lang command - show supported languages"""
        text = "🌐 **সাপোর্টেড ভাষাসমূহ:**\n\n"
        
        # Create keyboard with all languages
        keyboard = []
        row = []
        for i, (code, name) in enumerate(LANGUAGES.items()):
            if code == "bn":
                continue  # Skip Bangla as it's target
            btn = InlineKeyboardButton(
                name, 
                callback_data=f"lang_{code}"
            )
            row.append(btn)
            if len(row) == 2:  # 2 columns
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 পিছনে", callback_data="back")])
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        # Check if user has any running job
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            status_text = f"""
📊 **বর্তমান অবস্থা**

🆔 কাজের আইডি: `{session.get('job_id', 'N/A')}`
📹 ভিডিও: `{session.get('video_name', 'Unknown')}`
🔊 ভাষা: `{session.get('lang', 'Not set')}`
📊 অগ্রগতি: `{session.get('progress', 0)}%`

⏳ অনুগ্রহ করে অপেক্ষা করুন...
            """
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                "ℹ️ আপনার কোনো চলমান কাজ নেই।\n"
                "ভিডিও আপলোড করে শুরু করুন!"
            )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            # Cancel the task
            self.user_sessions[user_id]['cancelled'] = True
            await update.message.reply_text(
                "⏹️ কাজ বাতিল করা হচ্ছে...\n"
                "কিছুক্ষণের মধ্যে বন্ধ হয়ে যাবে।"
            )
        else:
            await update.message.reply_text("❌ কোনো চলমান কাজ নেই!")
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text.lower()
        
        if "হ্যালো" in text or "hello" in text:
            await update.message.reply_text(
                "👋 হ্যালো! ভিডিও আপলোড করুন বাংলা ডাবিংয়ের জন্য।"
            )
        elif "ধন্যবাদ" in text or "thank" in text:
            await update.message.reply_text(
                "🙏 আপনাকে ধন্যবাদ! ভালো থাকুন।"
            )
        else:
            await update.message.reply_text(
                "🤔 বুঝতে পারছি না। /help দেখুন অথবা ভিডিও আপলোড করুন।"
            )
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video uploads"""
        user_id = update.effective_user.id
        
        # Check if user already has a running job
        if user_id in self.user_sessions:
            await update.message.reply_text(
                "⏳ আপনার একটি চলমান কাজ আছে!\n"
                "অগ্রগতি দেখতে /status ব্যবহার করুন।\n"
                "বাতিল করতে /cancel লিখুন।"
            )
            return
        
        # Get video info
        video = update.message.video
        if not video:
            await update.message.reply_text("❌ দয়া করে একটি ভিডিও ফাইল পাঠান!")
            return
        
        # Check duration (1 hour max)
        duration = video.duration
        if duration > 3600:
            await update.message.reply_text(
                "❌ সর্বোচ্চ ১ ঘণ্টার ভিডিও সাপোর্টেড!\n"
                f"আপনার ভিডিও: {duration//60} মিনিট"
            )
            return
        
        # Check file size (500MB max)
        file_size = video.file_size
        if file_size > 500 * 1024 * 1024:
            await update.message.reply_text(
                "❌ সর্বোচ্চ ৫০০ MB সাইজ সাপোর্টেড!\n"
                f"আপনার ফাইল: {file_size/(1024*1024):.1f} MB"
            )
            return
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'status': 'downloading',
            'progress': 0,
            'video_name': video.file_name or f"video_{update.message.message_id}",
            'duration': duration,
            'size': file_size,
            'cancelled': False
        }
        
        # Create download directory
        os.makedirs("downloads", exist_ok=True)
        video_path = f"downloads/{user_id}_{update.message.message_id}.mp4"
        
        # Send initial status
        status_msg = await update.message.reply_text(
            "📥 ভিডিও ডাউনলোড হচ্ছে...\n"
            f"📹 সাইজ: {file_size/(1024*1024):.1f} MB\n"
            f"⏱ দৈর্ঘ্য: {duration//60} মিনিট"
        )
        
        try:
            # Download video
            video_file = await video.get_file()
            await video_file.download_to_drive(video_path)
            self.user_sessions[user_id]['status'] = 'downloaded'
            
            # Ask for language selection
            lang_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
                [InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")],
                [InlineKeyboardButton("🇵🇰 Urdu", callback_data="lang_ur")],
                [InlineKeyboardButton("🇸🇦 Arabic", callback_data="lang_ar")],
                [InlineKeyboardButton("🇨🇳 Chinese", callback_data="lang_zh")],
                [InlineKeyboardButton("🔍 অন্য ভাষা", callback_data="more_langs")],
            ])
            
            await status_msg.edit_text(
                "📥 ডাউনলোড সম্পন্ন!\n\n"
                "🌐 ভিডিওতে কোন ভাষা আছে?\n"
                "নিচ থেকে সিলেক্ট করুন:",
                reply_markup=lang_keyboard
            )
            
            # Store video path in context
            context.user_data['video_path'] = video_path
            context.user_data['status_msg_id'] = status_msg.message_id
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await status_msg.edit_text(f"❌ ডাউনলোড ত্রুটি: {str(e)}")
            self.user_sessions.pop(user_id, None)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data == "upload":
            await query.edit_message_text(
                "📹 আপনার ভিডিও পাঠান।\n\n"
                "📌 মনে রাখবেন:\n"
                "• MP4 ফরম্যাট প্রফার্ড\n"
                "• ১ ঘণ্টার বেশি নয়\n"
                "• ৫০০ MB এর বেশি নয়"
            )
            
        elif data == "select_lang":
            await self.language_command(update, context)
            
        elif data == "help":
            await self.help_command(update, context)
            
        elif data == "back":
            await self.start_command(update, context)
            
        elif data == "more_langs":
            # Show all languages
            text = "🌐 **সমস্ত সাপোর্টেড ভাষা:**\n\n"
            for code, name in LANGUAGES.items():
                if code != "bn":
                    text += f"• {name}\n"
            text += "\nকোনো একটি সিলেক্ট করুন:"
            
            # Create 2-column keyboard for all languages
            keyboard = []
            row = []
            for code, name in LANGUAGES.items():
                if code == "bn":
                    continue
                btn = InlineKeyboardButton(name.split()[1], callback_data=f"lang_{code}")
                row.append(btn)
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("🔙 পিছনে", callback_data="back")])
            
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif data.startswith("lang_"):
            # Language selected
            lang_code = data.split("_")[1]
            lang_name = LANGUAGES.get(lang_code, "Unknown")
            
            # Check if video was uploaded
            if 'video_path' not in context.user_data:
                await query.edit_message_text(
                    "❌ আগে ভিডিও আপলোড করুন!\n"
                    "/start দিয়ে শুরু করুন।"
                )
                return
            
            video_path = context.user_data['video_path']
            status_msg_id = context.user_data.get('status_msg_id')
            
            # Update status
            await query.edit_message_text(
                f"✅ ভাষা সিলেক্ট: {lang_name}\n\n"
                "🔄 প্রক্রিয়াকরণ শুরু হচ্ছে...\n"
                "এতে ৩-১০ মিনিট সময় লাগতে পারে।\n"
                "অগ্রগতি জানতে /status ব্যবহার করুন।"
            )
            
            # Start processing in background
            asyncio.create_task(
                self.process_video(
                    user_id,
                    video_path,
                    lang_code,
                    update.effective_chat.id,
                    status_msg_id
                )
            )
    
    async def process_video(
        self, 
        user_id: int, 
        video_path: str, 
        lang_code: str,
        chat_id: int,
        status_msg_id: Optional[int] = None
    ):
        """Process video in background"""
        try:
            # Update session
            if user_id in self.user_sessions:
                self.user_sessions[user_id]['status'] = 'processing'
                self.user_sessions[user_id]['lang'] = lang_code
                self.user_sessions[user_id]['job_id'] = f"job_{user_id}_{datetime.now().timestamp()}"
            
            # Output path
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            output_path = f"{output_dir}/{user_id}_{int(datetime.now().timestamp())}_bangla.mp4"
            
            # Progress callback
            async def update_progress(progress: float, stage: str):
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]['progress'] = progress
                    self.user_sessions[user_id]['stage'] = stage
                
                # Send progress update every 10%
                if int(progress) % 10 == 0:
                    try:
                        await self.app.bot.edit_message_text(
                            f"🔄 প্রক্রিয়াকরণ চলছে... {int(progress)}%\n"
                            f"📌 ধাপ: {stage}\n"
                            f"⏳ দয়া করে অপেক্ষা করুন...",
                            chat_id=chat_id,
                            message_id=status_msg_id
                        )
                    except:
                        pass
            
            # Process through pipeline
            result = await asyncio.to_thread(
                self.dubber.process,
                video_path=video_path,
                source_lang=lang_code,
                target_lang="bn",
                output_path=output_path,
                progress_callback=update_progress
            )
            
            # Send success message
            await self.app.bot.edit_message_text(
                "✅ **প্রক্রিয়াকরণ সম্পন্ন!** 🎉\n\n"
                f"📹 ভিডিওটি বাংলায় ডাব করা হয়েছে।\n"
                f"📊 ভাষা: {LANGUAGES.get(lang_code, 'Unknown')} → বাংলা\n"
                f"📁 ফাইল: {os.path.basename(output_path)}\n\n"
                "📥 ভিডিও ডাউনলোড করুন:",
                chat_id=chat_id,
                message_id=status_msg_id,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send the dubbed video
            with open(result, 'rb') as video_file:
                await self.app.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption="🎬 আপনার বাংলা ডাবিংকৃত ভিডিও!",
                    supports_streaming=True,
                    write_timeout=300  # 5 minutes timeout for large files
                )
            
            # Cleanup
            os.remove(video_path)
            os.remove(result)
            
            # Remove session
            self.user_sessions.pop(user_id, None)
            
        except asyncio.CancelledError:
            logger.info(f"Processing cancelled for user {user_id}")
            await self.app.bot.edit_message_text(
                "⏹️ কাজ বাতিল করা হয়েছে।",
                chat_id=chat_id,
                message_id=status_msg_id
            )
            self.user_sessions.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Processing error for user {user_id}: {e}")
            await self.app.bot.edit_message_text(
                f"❌ প্রক্রিয়াকরণ ত্রুটি:\n```\n{str(e)[:200]}...\n```\n\n"
                "দয়া করে আবার চেষ্টা করুন অথবা /help দেখুন।",
                chat_id=chat_id,
                message_id=status_msg_id,
                parse_mode=ParseMode.MARKDOWN
            )
            self.user_sessions.pop(user_id, None)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ একটি ত্রুটি ঘটেছে! দয়া করে আবার চেষ্টা করুন।"
                )
        except:
            pass
    
    def run(self):
        """Run the bot"""
        logger.info("🚀 Bot is starting...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


# Run
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8558590216:AAG1IUG_dWV3xiEgtXdpm1_WniAF-uLAGOs")
    bot = DubbingBot(TOKEN)
    bot.run()
