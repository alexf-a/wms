from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Bin
from faker import Faker
import qrcode
from django.core.files.base import ContentFile
from io import BytesIO
import boto3
import json

class Command(BaseCommand):
    help = "Create fake bins for testing"

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, help="Number of bins to create")
        parser.add_argument('--username', '-u', type=str, required=True, help="Username of the owner")

    def handle(self, *args, **options):
        fake = Faker()
        # Initialize AWS Bedrock client for Claude model
        bedrock = boto3.client('bedrock-runtime')
        user_model = get_user_model()
        username = options.get("username")
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found."))
            return

        count = options['count']
        for _ in range(count):
            # Generate bin name via AWS Bedrock Claude with high temperature
            name_prompt = (
                "Generate a creative storage bin name related to hobbies, seasonal events, or home maintenance. "
                "Provide only the name."
            )
            response = bedrock.invoke_model(
                modelId="anthropic.claude-3-5-haiku-20241022-v1:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "prompt": name_prompt,
                    "temperature": 0.8,
                    "max_tokens": 10,
                    "stop_sequences": ["\n"]
                })
            )
            name = json.loads(response['body'].read())['results'][0]['generation'].strip().capitalize()
            # Generate description based on generated name
            desc_prompt = f"Imagine you are a home-owner who is organizing their belongings into bins. Generate a concise description for a storage bin named '{name}'."
            response = bedrock.invoke_model(
                modelId="anthropic.claude-3-5-haiku-20241022-v1:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "prompt": desc_prompt,
                    "temperature": 0.7,
                    "max_tokens": 50,
                    "stop_sequences": ["\n"]
                })
            )
            description = json.loads(response['body'].read())['results'][0]['generation'].strip()
            location = fake.city()
            length = round(fake.random_number(digits=2) + fake.random.random(), 2)
            width = round(fake.random_number(digits=2) + fake.random.random(), 2)
            height = round(fake.random_number(digits=2) + fake.random.random(), 2)

            bin_obj = Bin(
                user=user,
                name=name,
                description=description,
                location=location,
                length=length,
                width=width,
                height=height,
            )
            bin_obj.save()

            qr_img = qrcode.make(name)
            buffer = BytesIO()
            qr_img.save(buffer, format='PNG')
            buffer.seek(0)
            file_name = f"{name}_qr.png"
            bin_obj.qr_code.save(file_name, ContentFile(buffer.read()), save=True)

            self.stdout.write(self.style.SUCCESS(f"Created Bin: {bin_obj.name}"))