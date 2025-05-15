from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('website_app', '0022_message_edited_at_message_is_edited_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop all chat-related tables and reset their migration state
            """
            DROP TABLE IF EXISTS "Chat_participants";
            DROP TABLE IF EXISTS "Message_read_by";
            DROP TABLE IF EXISTS "Chat";
            DROP TABLE IF EXISTS "Message";
            DROP TABLE IF EXISTS "ChatParticipant";
            DROP TABLE IF EXISTS "NewChatParticipant";
            DROP TABLE IF EXISTS "chat";
            DROP TABLE IF EXISTS "message";
            DROP TABLE IF EXISTS "chatparticipant";
            DROP TABLE IF EXISTS "newchatparticipant";
            DELETE FROM django_migrations WHERE app = 'website_app' AND name IN (
                '0023_remove_message_chat_remove_chatparticipant_chat_and_more',
                '0024_remove_chat_models'
            );
            """,
            # No reverse SQL needed since we're removing tables
            reverse_sql=""
        ),
    ] 