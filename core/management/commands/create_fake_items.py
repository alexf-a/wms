from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Bin, Item
from faker import Faker
import random
import requests
from django.core.files.base import ContentFile
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import logging
import time
import boto3
import base64
import json

class Command(BaseCommand):
    help = "Create fake items with matching images for testing"

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, help="Number of items to create per bin")
        parser.add_argument('--username', '-u', type=str, required=True, help="Username of the bin owner")
        parser.add_argument('--all-bins', '-a', action='store_true', help="Create items for all user's bins")
        parser.add_argument('--bin-name', '-b', type=str, help="Name of specific bin to populate")

    def handle(self, *args, **options):
        fake = Faker()
        user_model = get_user_model()
        username = options.get("username")
        count = options['count']
        bin_name = options.get('bin_name')
        all_bins = options.get('all_bins')
        
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{username}' not found."))
            return
        
        # Get bins to populate
        if bin_name:
            try:
                bins = [Bin.objects.get(user=user, name=bin_name)]
            except Bin.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Bin '{bin_name}' not found for user '{username}'."))
                return
        elif all_bins:
            bins = Bin.objects.filter(user=user)
            if not bins.exists():
                self.stdout.write(self.style.ERROR(f"No bins found for user '{username}'."))
                return
        else:
            bins = Bin.objects.filter(user=user).order_by('?')[:1]
            if not bins:
                self.stdout.write(self.style.ERROR(f"No bins found for user '{username}'."))
                return
        
        # Define realistic item categories and items
        item_categories = {
            "Kitchen": ["Blender", "Toaster", "Coffee Maker", "Food Processor", "Knife Set", 
                      "Measuring Cups", "Baking Sheet", "Mixing Bowl", "Dutch Oven", "Cutting Board"],
            "Electronics": ["Headphones", "External Hard Drive", "USB Cable", "Laptop Charger", 
                          "Power Bank", "Wireless Mouse", "Keyboard", "Webcam", "Bluetooth Speaker", "HDMI Cable"],
            "Books": ["Fiction Novel", "Cookbook", "Self-Help Book", "Biography", "Reference Book", 
                    "Magazine Collection", "Comic Book", "Textbook", "Photo Album", "Journal"],
            "Clothing": ["Winter Coat", "Summer Dress", "Denim Jacket", "Running Shoes", 
                       "Hiking Boots", "Sweater", "Scarf", "Gloves", "Hat", "Formal Suit"],
            "Tools": ["Hammer", "Screwdriver Set", "Cordless Drill", "Level", "Measuring Tape", 
                    "Wrench Set", "Pliers", "Hex Key Set", "Hand Saw", "Power Sander"],
            "Sports": ["Tennis Racket", "Basketball", "Yoga Mat", "Dumbbells", "Bicycle Pump", 
                      "Hiking Backpack", "Swimming Goggles", "Golf Clubs", "Running Shoes", "Fitness Tracker"],
            "Décor": ["Picture Frame", "Wall Clock", "Decorative Pillow", "Vase", "Candle Set", 
                     "Table Lamp", "Wall Art", "Plant Pot", "Throw Blanket", "Ornamental Box"],
            "Office": ["Stapler", "Notebook", "Desk Organizer", "Paper Clips", "Sticky Notes", 
                      "Fountain Pen", "File Folders", "Desk Lamp", "Calculator", "Planner"],
            "Toys": ["Board Game", "Puzzle", "Action Figure", "Building Blocks", "Remote Control Car", 
                   "Stuffed Animal", "Card Game", "Art Supplies", "Doll", "Science Kit"],
            "Seasonal": ["Christmas Ornaments", "Halloween Decorations", "Easter Basket", 
                       "Valentine's Day Cards", "Birthday Party Supplies", "Fourth of July Flags", 
                       "Thanksgiving Décor", "New Year's Eve Supplies", "Back-to-School Kit", "Beach Umbrella"]
        }
        
        # Generate fake items for each bin
        for storage_bin in bins:
            category_keys = list(item_categories.keys())
            
            # Assign 1-3 primary categories to this bin
            bin_categories = random.sample(category_keys, min(random.randint(1, 3), len(category_keys)))
            
            self.stdout.write(self.style.SUCCESS(f"Creating {count} items for bin: {storage_bin.name}"))
            self.stdout.write(f"  Primary categories: {', '.join(bin_categories)}")
            
            for _ in range(count):
                # 80% chance to pick from primary categories, 20% chance for random category
                if random.random() < 0.8:
                    category = random.choice(bin_categories)
                else:
                    category = random.choice(category_keys)
                    
                # Get a random item name from the category
                available_items = item_categories[category]
                item_name = random.choice(available_items)
                
                # Add some variation to make items unique
                if random.random() < 0.7:  # 70% chance to add variation
                    variation = random.choice([
                        f"{fake.color_name()} ",
                        f"{fake.word().capitalize()} ",
                        f"Vintage ",
                        f"Small ",
                        f"Large ",
                        f"Premium ",
                        f"Old ",
                        f"New ",
                        f"{fake.company_suffix()} "
                    ])
                    item_name = f"{variation}{item_name}"
                
                description = fake.paragraph(nb_sentences=3)
                
                # Create the item
                item = Item(
                    name=item_name,
                    description=description,
                    bin=storage_bin
                )
                item.save()
                
                # Generate image via AWS Bedrock using text-to-image
                image_success = False
                try:
                    client = boto3.client("bedrock-runtime")
                    body = {
                        "prompt": f"Generate an image of {item_name}",
                        "mode": "text-to-image",
                        "aspect_ratio": "1:1",
                        "output_format": "jpeg"
                    }
                    response = client.invoke_model(
                        modelId="stability.sd3-5-large-v1:0",
                        contentType="application/json",
                        accept="application/json",
                        body=json.dumps(body)
                    )
                    result = json.loads(response['body'].read().decode('utf-8'))
                    if "images" in result and result["images"]:
                        img_b64 = result["images"][0]
                        img_data = base64.b64decode(img_b64)
                        file_name = f"{item_name.replace(' ', '_')}.jpg"
                        item.image.save(file_name, ContentFile(img_data), save=True)
                        image_success = True
                    else:
                        raise ValueError("No images returned from Bedrock.")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed to generate image via Bedrock for {item_name}: {str(e)}"))

                # If downloading failed, generate a placeholder image with item name
                if not image_success:
                    try:
                        # Create a colored background image based on category
                        width, height = 400, 300
                        bg_color = category_colors.get(category, (200, 200, 200))  # Default gray if category not found
                        img = Image.new('RGB', (width, height), color=bg_color)
                        
                        # Add text
                        draw = ImageDraw.Draw(img)
                        
                        # Draw item name in center
                        text_color = (30, 30, 30)  # Dark gray, nearly black
                        
                        # Calculate font size based on text length
                        font_size = min(36, int(300 / (len(item_name) / 10)))  # Adjust font size based on text length
                        
                        try:
                            # Try to use ImageFont if available
                            try:
                                font = ImageFont.truetype("Arial", font_size)
                            except IOError:
                                font = ImageFont.load_default()
                                
                            # Draw text in the center
                            text_width, text_height = draw.textbbox((0, 0), item_name, font=font)[2:4]
                            position = ((width - text_width) // 2, (height - text_height) // 2)
                            draw.text(position, item_name, fill=text_color, font=font)
                            
                            # Draw category name at bottom
                            category_position = (10, height - 30)
                            draw.text(category_position, category, fill=text_color, font=font)
                        except AttributeError:
                            # Fallback for older PIL versions
                            text_width, text_height = width//2, height//3
                            position = ((width - text_width) // 2, (height - text_height) // 2)
                            draw.text(position, item_name, fill=text_color)
                            
                            # Draw category name at bottom
                            category_position = (10, height - 30)
                            draw.text(category_position, category, fill=text_color)
                        
                        # Save the image
                        output = BytesIO()
                        img.save(output, format='JPEG', quality=90)
                        output.seek(0)
                        
                        file_name = f"{item_name.replace(' ', '_')}_generated.jpg"
                        item.image.save(file_name, ContentFile(output.read()), save=True)
                        image_success = True
                    except Exception as e:
                        # Delete the item if we couldn't create an image
                        item.delete()
                        self.stdout.write(self.style.ERROR(f"Failed to generate image for {item_name}, item not created: {str(e)}"))
                        continue  # Skip to the next item
                
                if not image_success:
                    # This is a safeguard in case both methods fail - delete the item
                    item.delete()
                    self.stdout.write(self.style.ERROR(f"Could not create or download an image for {item_name}. Item not created."))
                    continue
                    
                self.stdout.write(self.style.SUCCESS(f"  Created Item: {item.name} in {category} category"))