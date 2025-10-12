# Generated manually to fix foreign key constraints

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_alter_customuser_password'),
    ]

    operations = [
        # Удаляем старые constraints на auth_user
        migrations.RunSQL(
            sql="""
                ALTER TABLE main_calculationtco 
                DROP CONSTRAINT IF EXISTS main_calculation_creator_id_74ce2a03_fk_auth_user_id;
            """,
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE main_calculationtco 
                DROP CONSTRAINT IF EXISTS main_calculation_moderator_id_e5f8b9c4_fk_auth_user_id;
            """,
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Создаём новые constraints на main_customuser
        migrations.RunSQL(
            sql="""
                ALTER TABLE main_calculationtco 
                ADD CONSTRAINT main_calculationtco_creator_id_fk_customuser 
                FOREIGN KEY (creator_id) REFERENCES main_customuser(id) 
                DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
                ALTER TABLE main_calculationtco 
                DROP CONSTRAINT main_calculationtco_creator_id_fk_customuser;
            """
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE main_calculationtco 
                ADD CONSTRAINT main_calculationtco_moderator_id_fk_customuser 
                FOREIGN KEY (moderator_id) REFERENCES main_customuser(id) 
                DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
                ALTER TABLE main_calculationtco 
                DROP CONSTRAINT main_calculationtco_moderator_id_fk_customuser;
            """
        ),
    ]
