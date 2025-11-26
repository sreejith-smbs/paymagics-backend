

class AdminRouter:
    """
    Router to ensure admin-related models always use public schema
    """
    admin_models = {
        'admin', 'auth', 'contenttypes', 'sessions'
    }

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.admin_models:
            return 'default'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.admin_models:
            return 'default'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations between objects in public schema
        if (obj1._meta.app_label in self.admin_models and
                obj2._meta.app_label in self.admin_models):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Admin models should only be migrated to default database
        if app_label in self.admin_models:
            return db == 'default'
        return None