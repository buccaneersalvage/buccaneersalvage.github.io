#!/usr/bin/env python3
"""
Restore missing photos from eBay archive to GitHub Buccaneer store.

This script identifies items in the Square catalog that are missing photos
and restores them from the local eBay archive on the office PC.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
import urllib.request

# Configuration
GITHUB_STORE = Path("/home/jollyroge1480/sites/buccaneersalvage-hub")
OFFICE_IP = "10.0.0.39"
CATALOG_FILE = GITHUB_STORE / "assets/square-catalog.json"
PDP_GALLERY = GITHUB_STORE / "assets/pdp-gallery"
PRODUCT_THUMBS = GITHUB_STORE / "assets/product-thumbs"

def get_missing_photo_items():
    """Identify items in catalog that are missing photos."""
    with open(CATALOG_FILE, 'r') as f:
        catalog = json.load(f)
    
    missing = []
    for item in catalog['items']:
        images = item.get('images', [])
        if not images or len(images) == 0:
            missing.append({
                'id': item['id'],
                'name': item['name'],
                'ebay_item_id': item.get('ebay_item_id', ''),
                'main_image': item.get('image', '')
            })
    
    return missing

def check_ebay_archive_photos(ebay_item_id, item_name):
    """Check if photos exist in eBay archive for a given item."""
    try:
        # First try by eBay ID
        result = subprocess.run(
            ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/{ebay_item_id}-*/photos/ebay-hires 2>/dev/null || ls -d ~/ebay/listings/listed/{ebay_item_id}-*/photos/_originals 2>/dev/null'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, 'ebay_id'
        
        # If not found by eBay ID, try by item name (slug)
        slug = item_name.lower().replace(' ', '-').replace('_', '-')[:50]
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        result = subprocess.run(
            ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/{slug}*/photos/ebay-hires 2>/dev/null || ls -d ~/ebay/listings/listed/{slug}*/photos/_originals 2>/dev/null'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, 'slug'
        
        # Try extracting part number from item name and search for folders containing it
        # Extract potential part numbers (alphanumeric sequences, prioritize longer ones)
        import re
        part_numbers = re.findall(r'\b[A-Z0-9]{5,}\b', item_name)  # Look for 5+ char part numbers
        for pn in part_numbers:
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/*{pn}*carlson*/photos/ebay-hires 2>/dev/null || ls -d ~/ebay/listings/listed/*{pn}*/photos/ebay-hires 2>/dev/null'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, f'part_number_{pn}'
        
        # Fallback: try 4+ char part numbers if no 5+ found
        if not part_numbers:
            part_numbers = re.findall(r'\b[A-Z0-9]{4,}\b', item_name)
            for pn in part_numbers:
                result = subprocess.run(
                    ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/*{pn}*/photos/ebay-hires 2>/dev/null || ls -d ~/ebay/listings/listed/*{pn}*/photos/_originals 2>/dev/null'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, f'part_number_{pn}'
        
        return False, None
    except Exception as e:
        print(f"Error checking archive for {ebay_item_id}: {e}")
        return False, None

def get_ebay_photos(ebay_item_id, item_name):
    """Get photo paths from eBay archive."""
    import re
    try:
        # First try by eBay ID
        result = subprocess.run(
            ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/{ebay_item_id}-*/photos/ebay-hires -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = result.stdout.strip().split('\n')
            return [p.split('/')[-1] for p in paths if p], 'ebay_id'
        
        # Fallback to photos/_originals if ebay-hires doesn't exist
        result = subprocess.run(
            ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/{ebay_item_id}-*/photos/_originals -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = result.stdout.strip().split('\n')
            return [p.split('/')[-1] for p in paths if p], 'ebay_id'
        
        # Try by item name (slug)
        slug = item_name.lower().replace(' ', '-').replace('_', '-')[:50]
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        result = subprocess.run(
            ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/{slug}*/photos/ebay-hires -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = result.stdout.strip().split('\n')
            return [p.split('/')[-1] for p in paths if p], 'slug'
        
        result = subprocess.run(
            ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/{slug}*/photos/_originals -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = result.stdout.strip().split('\n')
            return [p.split('/')[-1] for p in paths if p], 'slug'
        
        # Try by part number (prioritize longer, more specific part numbers)
        part_numbers = re.findall(r'\b[A-Z0-9]{5,}\b', item_name)
        for pn in part_numbers:
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/*{pn}*/photos/ebay-hires -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                paths = result.stdout.strip().split('\n')
                return [p.split('/')[-1] for p in paths if p], f'part_number_{pn}'
        
        for pn in part_numbers:
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/*{pn}*/photos/_originals -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                paths = result.stdout.strip().split('\n')
                return [p.split('/')[-1] for p in paths if p], f'part_number_{pn}'
        
        # Fallback: try 4+ char part numbers if no 5+ found
        part_numbers = re.findall(r'\b[A-Z0-9]{4,}\b', item_name)
        for pn in part_numbers:
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/*{pn}*/photos/ebay-hires -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                paths = result.stdout.strip().split('\n')
                return [p.split('/')[-1] for p in paths if p], f'part_number_{pn}'
        
        for pn in part_numbers:
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'find ~/ebay/listings/listed/*{pn}*/photos/_originals -name "*.jpg" -o -name "*.JPG" 2>/dev/null | head -10'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                paths = result.stdout.strip().split('\n')
                return [p.split('/')[-1] for p in paths if p], f'part_number_{pn}'
        
        return [], None
    except Exception as e:
        print(f"Error getting photos for {ebay_item_id}: {e}")
        return [], None

def download_photo_from_archive(remote_path, local_dest, ebay_item_id, item_name, search_type):
    """Download a photo from eBay archive via SCP."""
    import re
    try:
        if search_type == 'ebay_id':
            # Find the actual folder name since we don't know the exact slug
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/{ebay_item_id}-* 2>/dev/null'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0 or not result.stdout.strip():
                print(f"Error finding folder for {ebay_item_id}")
                return False
            
            folder = result.stdout.strip().split('/')[-1]
        elif search_type == 'slug':
            # Search by slug (item name)
            slug = item_name.lower().replace(' ', '-').replace('_', '-')[:50]
            slug = ''.join(c for c in slug if c.isalnum() or c == '-')
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/{slug}* 2>/dev/null'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0 or not result.stdout.strip():
                print(f"Error finding folder for slug {slug}")
                return False
            
            folder = result.stdout.strip().split('/')[-1]
        elif search_type.startswith('part_number_'):
            # Search by part number
            pn = search_type.replace('part_number_', '')
            result = subprocess.run(
                ['ssh', '10.0.0.39', f'ls -d ~/ebay/listings/listed/*{pn}* 2>/dev/null'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0 or not result.stdout.strip():
                print(f"Error finding folder for part number {pn}")
                return False
            
            folder = result.stdout.strip().split('/')[-1]
        else:
            print(f"Unknown search type: {search_type}")
            return False
        
        remote_full = f"10.0.0.39:~/ebay/listings/listed/{folder}/photos/ebay-hires/{remote_path}"
        subprocess.run(
            ['scp', remote_full, str(local_dest)],
            check=True,
            timeout=30
        )
        return True
    except Exception as e:
        print(f"Error downloading {remote_path}: {e}")
        return False

def create_pdp_gallery(item_id, photos, ebay_item_id, item_name, search_type):
    """Create PDP gallery directory and convert photos to WebP."""
    gallery_dir = PDP_GALLERY / item_id
    gallery_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert photos to WebP and rename
    for i, photo_path in enumerate(photos[:5], 1):  # Max 5 photos
        # Download photo
        temp_jpg = gallery_dir / f"temp_{i}.jpg"
        if download_photo_from_archive(photo_path, temp_jpg, ebay_item_id, item_name, search_type):
            # Convert to WebP using ImageMagick
            webp_path = gallery_dir / f"{i:02d}.webp"
            try:
                subprocess.run(
                    ['convert', str(temp_jpg), '-quality', '80', str(webp_path)],
                    check=True,
                    timeout=10
                )
                temp_jpg.unlink()  # Remove temp file
                print(f"  ✓ Photo {i} converted")
            except subprocess.CalledProcessError:
                # Fallback: just copy the JPG if conversion fails
                final_jpg = gallery_dir / f"{i:02d}.jpg"
                temp_jpg.rename(final_jpg)
                print(f"  ✓ Photo {i} (JPG fallback)")
        else:
            print(f"  ✗ Photo {i} failed to download")

def create_product_thumb(item_id, first_photo, ebay_item_id, item_name, search_type):
    """Create product thumbnail from first photo."""
    PRODUCT_THUMBS.mkdir(parents=True, exist_ok=True)
    thumb_path = PRODUCT_THUMBS / f"{item_id}.webp"
    thumb_jpg = PRODUCT_THUMBS / f"{item_id}.jpg"
    
    # Download first photo
    temp_jpg = PRODUCT_THUMBS / f"temp_{item_id}.jpg"
    if download_photo_from_archive(first_photo, temp_jpg, ebay_item_id, item_name, search_type):
        # Convert to 400x400 WebP thumbnail using ImageMagick
        try:
            subprocess.run(
                ['convert', str(temp_jpg), '-resize', '400x400', '-quality', '75', str(thumb_path)],
                check=True,
                timeout=10
            )
            temp_jpg.unlink()
            print(f"  ✓ Thumbnail created (WebP)")
        except subprocess.CalledProcessError:
            # Fallback: just copy the JPG if conversion fails
            temp_jpg.rename(thumb_jpg)
            print(f"  ✓ Thumbnail created (JPG fallback)")
    else:
        print(f"  ✗ Thumbnail failed")

def update_catalog_images(item_id, images):
    """Update catalog JSON with new image paths."""
    # Generate new image paths (check if WebP or JPG)
    gallery_dir = PDP_GALLERY / item_id
    new_images = []
    
    for i in range(1, min(len(images), 5) + 1):
        # Check if WebP exists, otherwise use JPG
        webp_path = gallery_dir / f"{i:02d}.webp"
        jpg_path = gallery_dir / f"{i:02d}.jpg"
        
        if webp_path.exists():
            new_images.append(f"../assets/pdp-gallery/{item_id}/{i:02d}.webp")
        elif jpg_path.exists():
            new_images.append(f"../assets/pdp-gallery/{item_id}/{i:02d}.jpg")
    
    # Update catalog
    with open(CATALOG_FILE, 'r') as f:
        catalog = json.load(f)
    
    for item in catalog['items']:
        if item['id'] == item_id:
            item['images'] = new_images
            break
    
    with open(CATALOG_FILE, 'w') as f:
        json.dump(catalog, f, indent=2)
    
    print(f"  ✓ Catalog updated with {len(new_images)} images")

def main():
    print("🔍 Identifying items with missing photos...")
    missing_items = get_missing_photo_items()
    print(f"Found {len(missing_items)} items with missing photos")
    
    if not missing_items:
        print("✓ All items have photos. Nothing to do.")
        return
    
    print("\n🔄 Restoring photos from eBay archive...")
    restored = 0
    failed = 0
    
    for item in missing_items:  # Process all items
        item_id = item['id']
        ebay_id = item['ebay_item_id']
        
        if not ebay_id:
            print(f"⚠️  {item_id}: No eBay ID, skipping")
            failed += 1
            continue
        
        print(f"\n📦 {item_id}: {item['name'][:50]}")
        
        # Check if photos exist in archive (try both eBay ID and item name)
        has_photos, search_type = check_ebay_archive_photos(ebay_id, item['name'])
        if not has_photos:
            print(f"  ✗ No photos found in archive")
            failed += 1
            continue
        
        # Get photo paths
        photos, found_type = get_ebay_photos(ebay_id, item['name'])
        if not photos:
            print(f"  ✗ Failed to get photo list")
            failed += 1
            continue
        
        print(f"  ✓ Found {len(photos)} photos in archive (by {found_type})")
        
        # Create PDP gallery
        create_pdp_gallery(item_id, photos, ebay_id, item['name'], found_type)
        
        # Create product thumbnail
        if photos:
            create_product_thumb(item_id, photos[0], ebay_id, item['name'], found_type)
        
        # Update catalog
        update_catalog_images(item_id, photos)
        
        restored += 1
    
    print(f"\n✓ Restored {restored} items")
    print(f"✗ Failed {failed} items")
    print(f"\n💡 To process all {len(missing_items)} items, edit this script and remove the [:10] limit")

if __name__ == '__main__':
    main()