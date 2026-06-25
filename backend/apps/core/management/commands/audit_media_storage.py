import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db.models import Q

from apps.accounts.models import ProviderProfile
from apps.catalog.models import Category, ServiceMedia
from apps.portfolio.models import PortfolioMedia
from apps.core.media import safe_delete_storage_object

User = get_user_model()


class Command(BaseCommand):
    help = "Audits database file references and compares them with storage objects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scan-orphans",
            action="store_true",
            help="Scan storage for orphan files under managed prefixes.",
        )
        parser.add_argument(
            "--delete-orphans",
            action="store_true",
            help="Enables orphan deletion mode (requires --scan-orphans and --confirm-delete-orphans).",
        )
        parser.add_argument(
            "--confirm-delete-orphans",
            action="store_true",
            help="Confirmation flag to actually execute orphan deletion.",
        )
        parser.add_argument(
            "--max-objects",
            type=int,
            default=10000,
            help="Maximum number of storage objects to scan during orphan search.",
        )
        parser.add_argument(
            "--prefix",
            action="append",
            choices=["avatars", "services", "portfolio", "categories"],
            dest="prefixes",
            help="Filter orphan scan to specific predefined prefixes.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Returns exit code 1 if any missing, duplicate, unsafe, or mismatch references are found.",
        )

    def handle(self, *args, **options):
        scan_orphans = options["scan_orphans"]
        delete_orphans = options["delete_orphans"]
        confirm_delete_orphans = options["confirm_delete_orphans"]
        max_objects = options["max_objects"]
        selected_prefixes = options["prefixes"]
        strict = options["strict"]

        # Validate arguments dependency
        if delete_orphans and not scan_orphans:
            raise CommandError("The --delete-orphans flag requires --scan-orphans to be set.")
        if confirm_delete_orphans and not delete_orphans:
            raise CommandError("The --confirm-delete-orphans flag requires --delete-orphans to be set.")

        self.stdout.write("Starting Media Storage Audit...")

        # 1. Audit Database references
        db_references_count = 0
        existing_count = 0
        missing_count = 0
        unsafe_paths_count = 0
        ownership_mismatch_count = 0
        duplicate_count = 0
        storage_error_count = 0

        # Map name -> list of (model_name, record_id)
        name_to_records = {}
        missing_records = []
        unsafe_records = []
        mismatch_records = []

        def sanitize_name(name):
            # Safe sanitization: replace uuid parts or numbers with asterisks, keep extension
            if not name:
                return ""
            parts = name.split("/")
            sanitized_parts = []
            for part in parts:
                if re.match(r"^[0-9]+$", part):
                    sanitized_parts.append("*")
                elif re.match(r"^[a-fA-F0-9\-]{36}$", part.split(".")[0]):
                    ext = part.split(".")[-1] if "." in part else ""
                    sanitized_parts.append(f"*-uuid.{ext}" if ext else "*-uuid")
                else:
                    sanitized_parts.append(part)
            return "/".join(sanitized_parts)

        def record_reference(name, model_label, record_id):
            nonlocal db_references_count
            db_references_count += 1
            if name not in name_to_records:
                name_to_records[name] = []
            name_to_records[name].append((model_label, record_id))

        def check_path_safety(name):
            if not name:
                return True
            # Leading slash or backslash
            if name.startswith("/") or name.startswith("\\"):
                return False
            # Backslashes anywhere
            if "\\" in name:
                return False
            # Traversal
            if ".." in name:
                return False
            # URL schemes
            if "://" in name or any(name.startswith(s) for s in ("http:", "https:", "ftp:")):
                return False
            # Absolute windows path (e.g. C:)
            if re.match(r"^[a-zA-Z]:", name):
                return False
            # Empty segments or trailing slashes
            if "//" in name or name.endswith("/") or name.endswith("\\"):
                return False
            return True

        # Audit User.avatar
        for u in User.objects.exclude(Q(avatar=None) | Q(avatar="")):
            name = u.avatar.name
            record_reference(name, "accounts.User", u.pk)
            
            # Unsafe checks
            if not check_path_safety(name):
                unsafe_paths_count += 1
                unsafe_records.append(("accounts.User", u.pk, name))
                continue
                
            # Ownership check: avatars/{user_id}/{uuid}.{ext}
            parts = name.split("/")
            ext = name.split(".")[-1].lower() if "." in name else ""
            if len(parts) != 3 or parts[0] != "avatars" or parts[1] != str(u.pk) or ext not in ("jpg", "jpeg", "png", "webp"):
                ownership_mismatch_count += 1
                mismatch_records.append(("accounts.User", u.pk, name, "Expected avatars/{user_id}/{uuid}.{ext}"))

        # Audit Category.icon
        for c in Category.objects.exclude(Q(icon=None) | Q(icon="")):
            name = c.icon.name
            record_reference(name, "catalog.Category", c.pk)
            
            if not check_path_safety(name):
                unsafe_paths_count += 1
                unsafe_records.append(("catalog.Category", c.pk, name))
                continue
                
            # Expected categories/{filename}
            parts = name.split("/")
            ext = name.split(".")[-1].lower() if "." in name else ""
            if len(parts) != 2 or parts[0] != "categories" or ext not in ("jpg", "jpeg", "png", "webp", "svg", "gif"):
                ownership_mismatch_count += 1
                mismatch_records.append(("catalog.Category", c.pk, name, "Expected categories/{filename}"))

        # Audit ServiceMedia.file
        for sm in ServiceMedia.objects.select_related("service__provider").exclude(Q(file=None) | Q(file="")):
            name = sm.file.name
            record_reference(name, "catalog.ServiceMedia", sm.pk)
            
            if not check_path_safety(name):
                unsafe_paths_count += 1
                unsafe_records.append(("catalog.ServiceMedia", sm.pk, name))
                continue
                
            # Expected services/{provider_id}/{service_id}/{uuid}.{ext}
            parts = name.split("/")
            ext = name.split(".")[-1].lower() if "." in name else ""
            provider_id = str(sm.service.provider.id) if sm.service and sm.service.provider else "unknown"
            service_id = str(sm.service_id)
            if len(parts) != 4 or parts[0] != "services" or parts[1] != provider_id or parts[2] != service_id or ext not in ("jpg", "jpeg", "png", "webp"):
                ownership_mismatch_count += 1
                mismatch_records.append(("catalog.ServiceMedia", sm.pk, name, f"Expected services/{provider_id}/{service_id}/{{uuid}}.{{ext}}"))

        # Audit PortfolioMedia.file
        for pm in PortfolioMedia.objects.select_related("item__provider_profile").exclude(Q(file=None) | Q(file="")):
            name = pm.file.name
            record_reference(name, "portfolio.PortfolioMedia", pm.pk)
            
            if not check_path_safety(name):
                unsafe_paths_count += 1
                unsafe_records.append(("portfolio.PortfolioMedia", pm.pk, name))
                continue
                
            # Expected portfolio/{provider_id}/{portfolio_item_id}/{uuid}.{ext}
            parts = name.split("/")
            ext = name.split(".")[-1].lower() if "." in name else ""
            provider_id = str(pm.item.provider_profile_id) if pm.item else "unknown"
            item_id = str(pm.item_id)
            if len(parts) != 4 or parts[0] != "portfolio" or parts[1] != provider_id or parts[2] != item_id or ext not in ("jpg", "jpeg", "png", "webp"):
                ownership_mismatch_count += 1
                mismatch_records.append(("portfolio.PortfolioMedia", pm.pk, name, f"Expected portfolio/{provider_id}/{item_id}/{{uuid}}.{{ext}}"))

        # 2. Check Existence & Duplicates
        all_referenced_names = set(name_to_records.keys())
        for name in all_referenced_names:
            records = name_to_records[name]
            if len(records) > 1:
                duplicate_count += len(records) - 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Duplicate reference: {sanitize_name(name)} is referenced by {records}"
                    )
                )

            # Check exists
            try:
                if default_storage.exists(name):
                    existing_count += 1
                else:
                    missing_count += 1
                    missing_records.append((records, name))
                    for model_label, record_id in records:
                        self.style.ERROR(
                            f"Missing object: Record {model_label} (ID: {record_id}) references missing file: {sanitize_name(name)}"
                        )
            except Exception as e:
                storage_error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Storage error while checking {sanitize_name(name)}: {str(e)}"
                    )
                )

        # 3. Scan Orphans
        orphan_files = []
        scan_incomplete = False

        if scan_orphans:
            self.stdout.write("Scanning storage for orphans...")
            # Managed prefixes to scan
            prefixes_to_scan = selected_prefixes or ["avatars", "services", "portfolio", "categories"]
            
            total_scanned_count = 0
            
            def walk_storage(prefix=""):
                nonlocal total_scanned_count, scan_incomplete
                if total_scanned_count >= max_objects:
                    scan_incomplete = True
                    return []
                
                try:
                    dirs, files = default_storage.listdir(prefix)
                except Exception as e:
                    # Report storage list error safely
                    self.stdout.write(self.style.ERROR(f"Storage error listing prefix '{prefix}': {str(e)}"))
                    return []
                
                collected_files = []
                for f in files:
                    if total_scanned_count >= max_objects:
                        scan_incomplete = True
                        break
                    path = f"{prefix}/{f}" if prefix else f
                    collected_files.append(path)
                    total_scanned_count += 1
                    
                if not scan_incomplete:
                    for d in dirs:
                        sub_prefix = f"{prefix}/{d}" if prefix else d
                        # Make sure we don't traverse outside managed prefixes if prefix is empty
                        if not prefix and sub_prefix not in prefixes_to_scan:
                            continue
                        sub_collected = walk_storage(sub_prefix)
                        collected_files.extend(sub_collected)
                        if scan_incomplete:
                            break
                return collected_files

            # Trigger scan under managed prefixes
            all_storage_files = []
            for p in prefixes_to_scan:
                if scan_incomplete:
                    break
                try:
                    # Check if prefix exists first, to avoid errors
                    dirs, files = default_storage.listdir(p)
                    # If listing works, recursively walk
                    all_storage_files.extend(walk_storage(p))
                except Exception:
                    # Prefix does not exist in storage yet, skip
                    pass

            # Detect orphans
            for path in all_storage_files:
                # Normalize path separators
                norm_path = path.replace("\\", "/")
                if norm_path not in all_referenced_names:
                    # Do not report category files as deletes, but count them as orphans
                    orphan_files.append(norm_path)

            self.stdout.write(f"Scanned {total_scanned_count} storage objects.")
            if scan_incomplete:
                self.stdout.write(self.style.WARNING("Warning: Scan limit reached. Scan is incomplete."))
            self.stdout.write(f"Found {len(orphan_files)} orphan storage object(s).")
            for o in orphan_files:
                self.stdout.write(f"  Orphan: {sanitize_name(o)}")

        # 4. Delete Orphans (Explicit Cleanup)
        deleted_count = 0
        deletion_errors = False

        if delete_orphans and confirm_delete_orphans and scan_orphans:
            # Exclude categories/ from auto deletion
            deletable_orphans = [o for o in orphan_files if not o.startswith("categories/")]
            self.stdout.write(f"Planning to delete {len(deletable_orphans)} orphan files (excluding categories/).")
            
            for o in deletable_orphans:
                success = safe_delete_storage_object(default_storage, o, context="audit_media_storage_orphan_cleanup")
                if success:
                    deleted_count += 1
                    self.stdout.write(f"Deleted orphan file: {sanitize_name(o)}")
                else:
                    deletion_errors = True
                    self.stdout.write(self.style.ERROR(f"Failed to delete orphan: {sanitize_name(o)}"))

        # Output Summary
        self.stdout.write("\n=== Media Audit Summary ===")
        self.stdout.write(f"Referenced objects: {db_references_count}")
        self.stdout.write(f"Existing objects: {existing_count}")
        self.stdout.write(f"Missing objects: {missing_count}")
        self.stdout.write(f"Duplicate references: {duplicate_count}")
        self.stdout.write(f"Unsafe paths: {unsafe_paths_count}")
        self.stdout.write(f"Ownership-path mismatches: {ownership_mismatch_count}")
        self.stdout.write(f"Storage errors: {storage_error_count}")
        if scan_orphans:
            self.stdout.write(f"Orphans detected: {len(orphan_files)}")
            if delete_orphans and confirm_delete_orphans:
                self.stdout.write(f"Orphans deleted: {deleted_count}")

        # Strict mode exit verification
        has_issues = (
            missing_count > 0
            or unsafe_paths_count > 0
            or ownership_mismatch_count > 0
            or duplicate_count > 0
            or storage_error_count > 0
            or scan_incomplete
            or deletion_errors
        )

        if strict and has_issues:
            raise CommandError("Audit failed: Database-to-storage inconsistencies or errors were detected.")
