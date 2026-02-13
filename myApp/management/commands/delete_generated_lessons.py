"""
Management command to delete AI-generated lessons and modules.

Usage:
    # Delete all generated lessons from a specific course
    python manage.py delete_generated_lessons --course aromatherapy-essential-oils

    # Delete lessons from a specific module
    python manage.py delete_generated_lessons --course aromatherapy-essential-oils --module "Aromatherapy Training"

    # Delete all generated lessons (all courses)
    python manage.py delete_generated_lessons --all

    # Delete empty modules after deleting lessons
    python manage.py delete_generated_lessons --course aromatherapy-essential-oils --delete-empty-modules

    # Delete all modules that contain generated lessons (and all their lessons)
    python manage.py delete_generated_lessons --course aromatherapy-essential-oils --delete-modules

    # Delete a specific module (and all its lessons)
    python manage.py delete_generated_lessons --course aromatherapy-essential-oils --module "Module Name" --delete-module

    # Dry run (preview what would be deleted)
    python manage.py delete_generated_lessons --course aromatherapy-essential-oils --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from myApp.models import Course, Module, Lesson


class Command(BaseCommand):
    help = 'Delete AI-generated lessons from courses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course',
            type=str,
            help='Course slug (e.g., aromatherapy-essential-oils)'
        )
        parser.add_argument(
            '--module',
            type=str,
            help='Module name (optional, filters by module)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete all generated lessons from all courses'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--delete-empty-modules',
            action='store_true',
            help='Delete modules that have no lessons after deleting generated lessons'
        )
        parser.add_argument(
            '--delete-module',
            action='store_true',
            help='Delete the specified module (and all its lessons)'
        )
        parser.add_argument(
            '--delete-modules',
            action='store_true',
            help='Delete all modules that contain generated lessons (even if they have other lessons)'
        )

    def handle(self, *args, **options):
        course_slug = options.get('course')
        module_name = options.get('module')
        delete_all = options.get('all', False)
        dry_run = options.get('dry_run', False)
        delete_empty_modules = options.get('delete_empty_modules', False)
        delete_module = options.get('delete_module', False)
        delete_modules = options.get('delete_modules', False)

        if not delete_all and not course_slug:
            raise CommandError('Either --course or --all must be provided')

        if delete_module and not module_name:
            raise CommandError('--delete-module requires --module to be specified')

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN MODE - No lessons or modules will be deleted\n'))

        if delete_all:
            # Delete all generated lessons
            lessons = Lesson.objects.filter(ai_generation_status__in=['generated', 'approved'])
            total_count = lessons.count()
            
            if total_count == 0:
                self.stdout.write(self.style.WARNING('No generated lessons found.'))
                
                # Check for empty modules if flag is set
                if delete_empty_modules:
                    all_empty_modules = []
                    for course in Course.objects.all():
                        empty_modules = [m for m in course.modules.all() if m.lessons.count() == 0]
                        all_empty_modules.extend(empty_modules)
                    
                    if all_empty_modules:
                        if dry_run:
                            self.stdout.write(f'\nWould delete {len(all_empty_modules)} empty module(s) from all courses:')
                            for module in all_empty_modules[:20]:
                                self.stdout.write(f'  - {module.course.name} > {module.name}')
                            if len(all_empty_modules) > 20:
                                self.stdout.write(f'  ... and {len(all_empty_modules) - 20} more')
                        else:
                            module_count = len(all_empty_modules)
                            for module in all_empty_modules:
                                module.delete()
                            self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted {module_count} empty module(s) from all courses'))
                return
            
            if dry_run:
                self.stdout.write(f'Would delete {total_count} lesson(s) from all courses:')
                for lesson in lessons[:20]:  # Show first 20
                    self.stdout.write(f'  - {lesson.course.name} > {lesson.module.name if lesson.module else "No Module"} > {lesson.title}')
                if total_count > 20:
                    self.stdout.write(f'  ... and {total_count - 20} more')
            else:
                # Track modules that will become empty
                modules_to_check = set()
                for lesson in lessons:
                    if lesson.module:
                        modules_to_check.add(lesson.module)
                
                lessons.delete()
                self.stdout.write(self.style.SUCCESS(f'✅ Deleted {total_count} generated lesson(s) from all courses'))
                
                # Handle module deletion
                if delete_modules:
                    # Delete all modules that contained generated lessons (and all their remaining lessons)
                    modules_to_delete = list(modules_to_check)
                    if modules_to_delete:
                        if dry_run:
                            self.stdout.write(f'\nWould delete {len(modules_to_delete)} module(s) and all their remaining lessons:')
                            for mod in modules_to_delete[:20]:
                                remaining_lessons = mod.lessons.count()
                                self.stdout.write(f'  - {mod.course.name} > {mod.name} ({remaining_lessons} remaining lesson(s))')
                            if len(modules_to_delete) > 20:
                                self.stdout.write(f'  ... and {len(modules_to_delete) - 20} more')
                        else:
                            module_count = len(modules_to_delete)
                            module_names = []
                            for mod in modules_to_delete:
                                module_names.append(f'{mod.course.name} > {mod.name}')
                                # Delete all remaining lessons in these modules first
                                mod.lessons.all().delete()
                                mod.delete()
                            self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted {module_count} module(s) and all their lessons:'))
                            for name in module_names[:10]:
                                self.stdout.write(f'  - {name}')
                            if len(module_names) > 10:
                                self.stdout.write(f'  ... and {len(module_names) - 10} more')
                elif delete_empty_modules:
                    # Check modules that had lessons deleted
                    empty_modules = [m for m in modules_to_check if m.lessons.count() == 0]
                    
                    if empty_modules:
                        module_count = len(empty_modules)
                        for module in empty_modules:
                            module.delete()
                        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {module_count} empty module(s)'))
        else:
            # Delete from specific course
            try:
                course = Course.objects.get(slug=course_slug)
            except Course.DoesNotExist:
                raise CommandError(f'Course not found: {course_slug}')

            # Filter lessons
            lessons = Lesson.objects.filter(
                course=course,
                ai_generation_status__in=['generated', 'approved']
            )

            module = None
            if module_name:
                try:
                    module = Module.objects.get(course=course, name=module_name)
                    if delete_module:
                        # Delete entire module (all lessons, not just generated ones)
                        module_lessons = module.lessons.all()
                        module_lesson_count = module_lessons.count()
                        
                        if dry_run:
                            self.stdout.write(f'\nWould delete module "{module_name}" and all {module_lesson_count} lesson(s) in it:')
                            for lesson in module_lessons[:10]:
                                self.stdout.write(f'  - {lesson.title}')
                            if module_lesson_count > 10:
                                self.stdout.write(f'  ... and {module_lesson_count - 10} more')
                        else:
                            module_lessons.delete()
                            module.delete()
                            self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted module "{module_name}" and {module_lesson_count} lesson(s)'))
                        return
                    else:
                        lessons = lessons.filter(module=module)
                        self.stdout.write(f'Filtering by module: {module_name}')
                except Module.DoesNotExist:
                    raise CommandError(f'Module not found: {module_name}')

            total_count = lessons.count()

            if total_count == 0:
                self.stdout.write(self.style.WARNING(f'No generated lessons found in {course.name}'))
                
                # Check for empty modules if flag is set
                if delete_empty_modules:
                    self._handle_empty_modules(course, dry_run)
                return

            if dry_run:
                self.stdout.write(f'\nWould delete {total_count} lesson(s) from "{course.name}":')
                for lesson in lessons:
                    module_info = f' > {lesson.module.name}' if lesson.module else ''
                    self.stdout.write(f'  - {lesson.title}{module_info}')
            else:
                lesson_titles = [lesson.title for lesson in lessons]
                deleted_modules = set()
                
                # Track which modules will become empty
                for lesson in lessons:
                    if lesson.module:
                        deleted_modules.add(lesson.module)
                
                lessons.delete()
                self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted {total_count} lesson(s) from "{course.name}":'))
                for title in lesson_titles[:10]:  # Show first 10
                    self.stdout.write(f'  - {title}')
                if len(lesson_titles) > 10:
                    self.stdout.write(f'  ... and {len(lesson_titles) - 10} more')
                
                # Handle module deletion
                if delete_modules:
                    # Delete all modules that contained generated lessons (and all their remaining lessons)
                    modules_to_delete = list(deleted_modules)
                    if modules_to_delete:
                        if dry_run:
                            self.stdout.write(f'\nWould delete {len(modules_to_delete)} module(s) and all their remaining lessons:')
                            for mod in modules_to_delete:
                                remaining_lessons = mod.lessons.count()
                                self.stdout.write(f'  - {mod.name} ({remaining_lessons} remaining lesson(s))')
                        else:
                            module_count = len(modules_to_delete)
                            module_names = [m.name for m in modules_to_delete]
                            for mod in modules_to_delete:
                                # Delete all remaining lessons in these modules first
                                mod.lessons.all().delete()
                                mod.delete()
                            self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted {module_count} module(s) and all their lessons:'))
                            for name in module_names:
                                self.stdout.write(f'  - {name}')
                elif delete_empty_modules:
                    self._handle_empty_modules(course, dry_run, deleted_modules)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  This was a dry run. Use without --dry-run to actually delete.'))

    def _handle_empty_modules(self, course, dry_run, modules_to_check=None):
        """Handle deletion of empty modules"""
        if modules_to_check:
            # Check specific modules
            empty_modules = [m for m in modules_to_check if m.lessons.count() == 0]
        else:
            # Check all modules in course
            empty_modules = [m for m in course.modules.all() if m.lessons.count() == 0]
        
        if not empty_modules:
            if dry_run:
                self.stdout.write('\nNo empty modules found.')
            return
        
        if dry_run:
            self.stdout.write(f'\nWould delete {len(empty_modules)} empty module(s):')
            for module in empty_modules:
                self.stdout.write(f'  - {module.name}')
        else:
            module_names = [m.name for m in empty_modules]
            for module in empty_modules:
                module.delete()
            self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted {len(empty_modules)} empty module(s):'))
            for name in module_names:
                self.stdout.write(f'  - {name}')

