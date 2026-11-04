from django.contrib.auth import get_user_model

from django.core.management.base import BaseCommand

from django.db import transaction



from apps.portal.models import PortalAccount

from apps.rbac.models import MembershipRole, Role

from apps.rbac.services import seed_system_roles

from apps.tenancy.models import Membership, Organization





class Command(BaseCommand):

    help = "Seeds standardized user credentials and role memberships for all system personas."



    def add_arguments(self, parser):

        parser.add_argument(

            "--password",

            default="Password123!",

            help="Default password for all seeded users (default: Password123!)",

        )



    @transaction.atomic

    def handle(self, *args, **options):

        password = options["password"]

        User = get_user_model()



        self.stdout.write(self.style.NOTICE("Initializing system roles & user credentials..."))



        # 1. Organization Setup

        org = Organization.objects.filter(name__iexact="Apex Industrial Technologies Ltd").first()

        if not org:

            org = Organization.objects.filter(slug="apex-industrial-technologies").first()

        if not org:

            org = Organization.objects.create(

                slug="apex-industrial-technologies",

                name="Apex Industrial Technologies Ltd",

                contact_email="operations@apexindustrial.example.com",

                contact_phone="+94 11 289 9000",

            )

        self.stdout.write(self.style.SUCCESS(f"[OK] Organization: {org.name} ({org.slug})"))



        # 2. Seed System Roles for the Organization

        roles_dict = seed_system_roles(org, prune_extra=True)

        self.stdout.write(self.style.SUCCESS(f"[OK] Seeded {len(roles_dict)} system roles"))



        # 3. Define Standard User Personas

        personas = [

            {

                "email": "owner@apexindustrial.example.com",

                "full_name": "Dinuka Wijesinghe",

                "job_title": "Managing Director / Owner",

                "role_key": "owner",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "admin@apexindustrial.example.com",

                "full_name": "Tharindu Alwis",

                "job_title": "IT & Systems Administrator",

                "role_key": "admin",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "ops.manager@apexindustrial.example.com",

                "full_name": "Anura Senanayake",

                "job_title": "Service Dispatcher",

                "role_key": "service_dispatcher",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "asset.manager@apexindustrial.example.com",

                "full_name": "Ruwan Jayasinghe",

                "job_title": "Principal Asset Manager",

                "role_key": "asset_manager",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "planner@apexindustrial.example.com",

                "full_name": "Nimali Fernando",

                "job_title": "Senior Maintenance Planner",

                "role_key": "maintenance_planner",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "supervisor@apexindustrial.example.com",

                "full_name": "Sunil Bandara",

                "job_title": "Maintenance Supervisor",

                "role_key": "supervisor",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "technician@apexindustrial.example.com",

                "full_name": "Kasun Perera",

                "job_title": "Lead Field Technician",

                "role_key": "technician",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "stores.manager@apexindustrial.example.com",

                "full_name": "Chaminda Silva",

                "job_title": "Inventory & Stores Manager",

                "role_key": "stores_manager",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "service.manager@apexindustrial.example.com",

                "full_name": "Pradeep Mendis",

                "job_title": "Service & SLA Manager",

                "role_key": "service_manager",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "auditor@apexindustrial.example.com",

                "full_name": "Shani De Silva",

                "job_title": "Compliance & Audit Officer",

                "role_key": "auditor",

                "is_platform_admin": False,

                "is_staff": False,

            },

            {

                "email": "client.requester@acmecorp.example.com",

                "full_name": "Raveen Fernando",

                "job_title": "Facility Manager (Acme Corp)",

                "role_key": "client_requester",

                "is_platform_admin": False,

                "is_staff": False,

                "is_portal_client": True,

            },

            {

                "email": "client.new@apexindustrial.com",

                "full_name": "Sarah Connor",

                "job_title": "Client Facility Manager",

                "role_key": "client_requester",

                "is_platform_admin": False,

                "is_staff": False,

                "is_portal_client": True,

            },

        ]



        # 4. Create Persona Users, Memberships & Assign Roles

        created_users = []

        for p in personas:

            email = p["email"]

            user = User.objects.filter(email__iexact=email).first()

            if not user:

                user = User.objects.create_user(

                    email=email,

                    password=password,

                    full_name=p["full_name"],

                    is_active=True,

                )

            else:

                user.set_password(password)

                user.full_name = p["full_name"]

                user.is_active = True

                user.save()



            # Membership in organization

            membership, _ = Membership.objects.unscoped().get_or_create(

                organization=org,

                user=user,

                defaults={"job_title": p["job_title"], "status": "ACTIVE"}

            )

            membership.status = "ACTIVE"

            membership.job_title = p["job_title"]

            membership.save()



            # Assign Role

            role = Role.objects.unscoped().filter(organization=org, system_key=p["role_key"]).first()

            if role:

                MembershipRole.objects.filter(membership=membership).exclude(role=role).delete()

                MembershipRole.objects.get_or_create(

                    membership=membership,

                    role=role,

                    defaults={"site": None}

                )



            # If portal client, setup PortalAccount & initial asset grant

            if p.get("is_portal_client"):

                portal_acc, _ = PortalAccount.objects.unscoped().get_or_create(

                    organization=org,

                    membership=membership,

                    defaults={"company_name": "Acme Corporation", "is_enabled": True}

                )

                from apps.assets.models import Asset

                from apps.portal.models import PortalAssetGrant

                first_asset = Asset.objects.filter(organization=org).exclude(status__in=["RETIRED", "DISPOSED"]).first()

                if first_asset:

                    PortalAssetGrant.objects.unscoped().get_or_create(

                        organization=org,

                        portal_account=portal_acc,

                        asset=first_asset,

                    )





            created_users.append({

                "role": role.name if role else p["role_key"],

                "role_key": p["role_key"],

                "email": email,

                "name": p["full_name"],

            })



        # 5. Provision Platform Super Administrator (DEF-05)

        platform_admin_email = "platform.admin@fieldops.io"

        p_admin = User.objects.filter(email__iexact=platform_admin_email).first()

        if not p_admin:

            p_admin = User.objects.create_user(

                email=platform_admin_email,

                password=password,

                full_name="Platform Super Administrator",

                is_active=True,

            )

        else:

            p_admin.set_password(password)

            p_admin.full_name = "Platform Super Administrator"

            p_admin.is_active = True

        p_admin.is_staff = True

        p_admin.is_superuser = True

        p_admin.is_platform_admin = True

        p_admin.save()

        self.stdout.write(self.style.SUCCESS(f"[OK] Provisioned Platform Super Admin: {platform_admin_email}"))



        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Successfully seeded all user credentials and roles!"))

