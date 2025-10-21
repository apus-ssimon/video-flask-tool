# kaltura_uploader.py - Kaltura API integration for Flask
import requests
import os
from urllib.parse import urlencode

# Kaltura API credentials
PARTNER_ID = '1147982'
ADMIN_SECRET = '3e836fc11231256fd81eece370549852'
USER_ID = 'ssimon@apus.edu'
SERVICE_URL = 'https://www.kaltura.com'
CATEGORY_3PLAY_ID = 44650131  # 3play category ID
CATEGORY_COURSE_TRAILER_ID = None  # Will be fetched or created

def create_kaltura_session():
    """Generate Kaltura session (KS)"""
    try:
        params = {
            'service': 'session',
            'action': 'start',
            'format': 1,
            'type': 2,  # ADMIN
            'partnerId': PARTNER_ID,
            'secret': ADMIN_SECRET,
            'userId': USER_ID,
        }
        
        response = requests.post(f'{SERVICE_URL}/api_v3/service/session/action/start', data=params)
        print('Kaltura session created')
        return response.text.strip('"')  # Remove quotes from response
    except Exception as e:
        print(f'Session creation error: {e}')
        raise Exception('Failed to create Kaltura session')

def upload_to_kaltura(ks, file_path, custom_name, tags):
    """Upload video file to Kaltura"""
    try:
        # Step 1: Get upload token
        token_params = {
            'ks': ks,
            'service': 'uploadtoken',
            'action': 'add',
            'format': 1
        }
        
        token_response = requests.post(f'{SERVICE_URL}/api_v3/service/uploadtoken/action/add', data=token_params)
        token_data = token_response.json()
        
        if not token_data.get('id'):
            raise Exception('Failed to get upload token')
        
        upload_token_id = token_data['id']
        print(f'Upload token created: {upload_token_id}')
        
        # Step 2: Upload the file
        with open(file_path, 'rb') as f:
            files = {'fileData': f}
            upload_data = {
                'ks': ks,
                'uploadTokenId': upload_token_id
            }
            
            upload_response = requests.post(
                f'{SERVICE_URL}/api_v3/service/uploadtoken/action/upload',
                data=upload_data,
                files=files
            )
            print('File uploaded to Kaltura')
        
        # Step 3: Create media entry
        all_tags = f'glitch, {tags}' if tags else 'glitch'
        
        media_params = {
            'ks': ks,
            'service': 'media',
            'action': 'add',
            'format': 1,
            'entry:mediaType': '1',  # Video
            'entry:name': custom_name,
            'entry:tags': all_tags
        }
        
        media_response = requests.post(f'{SERVICE_URL}/api_v3/service/media/action/add', data=media_params)
        media_data = media_response.json()
        
        if not media_data.get('id'):
            raise Exception('Failed to create media entry')
        
        entry_id = media_data['id']
        print(f'Media entry created: {entry_id}')
        
        # Step 4: Attach upload token to media entry
        add_content_params = {
            'ks': ks,
            'service': 'media',
            'action': 'addContent',
            'format': 1,
            'entryId': entry_id,
            'resource:objectType': 'KalturaUploadedFileTokenResource',
            'resource:token': upload_token_id
        }
        
        requests.post(f'{SERVICE_URL}/api_v3/service/media/action/addContent', data=add_content_params)
        print('Upload token attached to media entry')
        
        return entry_id
    except Exception as e:
        print(f'Upload error: {e}')
        raise Exception(f'Kaltura upload failed: {str(e)}')

def add_category_to_video(ks, video_id):
    """Add 3play and Course Trailer categories to video"""
    try:
        # Add 3play category
        assign_3play_params = {
            'ks': ks,
            'service': 'categoryentry',
            'action': 'add',
            'format': 1,
            'categoryEntry:categoryId': CATEGORY_3PLAY_ID,
            'categoryEntry:entryId': video_id
        }
        
        requests.post(f'{SERVICE_URL}/api_v3/service/categoryentry/action/add', data=assign_3play_params)
        print(f'3play category added to video {video_id}')
        
        # Get or create Course Trailer category
        course_trailer_id = get_or_create_course_trailer_category(ks)
        
        if course_trailer_id:
            # Add Course Trailer category
            assign_trailer_params = {
                'ks': ks,
                'service': 'categoryentry',
                'action': 'add',
                'format': 1,
                'categoryEntry:categoryId': course_trailer_id,
                'categoryEntry:entryId': video_id
            }
            
            requests.post(f'{SERVICE_URL}/api_v3/service/categoryentry/action/add', data=assign_trailer_params)
            print(f'Course Trailer category added to video {video_id}')
        
        return True
    except Exception as e:
        print(f'Category error: {e}')
        return False
    
def get_or_create_course_trailer_category(ks):
    """Get Course Trailer category ID or create it if it doesn't exist"""
    try:
        # First, try to find existing Course Trailer category
        list_params = {
            'ks': ks,
            'service': 'category',
            'action': 'list',
            'format': 1,
            'filter:fullNameEqual': 'Course Trailer'
        }
        
        list_response = requests.post(f'{SERVICE_URL}/api_v3/service/category/action/list', data=list_params)
        list_data = list_response.json()
        
        if list_data.get('objects') and len(list_data['objects']) > 0:
            category_id = list_data['objects'][0]['id']
            print(f'Found existing Course Trailer category: {category_id}')
            return category_id
        
        # If not found, create it
        create_params = {
            'ks': ks,
            'service': 'category',
            'action': 'add',
            'format': 1,
            'category:name': 'Course Trailer',
            'category:fullName': 'Course Trailer'
        }
        
        create_response = requests.post(f'{SERVICE_URL}/api_v3/service/category/action/add', data=create_params)
        create_data = create_response.json()
        
        if create_data.get('id'):
            category_id = create_data['id']
            print(f'Created Course Trailer category: {category_id}')
            return category_id
        
        return None
    except Exception as e:
        print(f'Error getting/creating Course Trailer category: {e}')
        return None

def request_captions(ks, entry_id):
    """Request automatic captions for video"""
    try:
        # Create Caption Asset
        create_params = {
            'ks': ks,
            'service': 'caption_captionasset',
            'action': 'add',
            'format': 1,
            'entryId': entry_id,
            'captionAsset:language': 'English',
            'captionAsset:format': '1',  # SRT format
            'captionAsset:label': 'English',
            'captionAsset:isDefault': '1'
        }
        
        asset_response = requests.post(f'{SERVICE_URL}/api_v3/service/caption_captionasset/action/add', data=create_params)
        asset_data = asset_response.json()
        
        if not asset_data.get('id'):
            print('Failed to create caption asset')
            return False
        
        caption_asset_id = asset_data['id']
        print(f'Caption asset created: {caption_asset_id}')
        
        # Get reach profile
        profile_params = {
            'ks': ks,
            'service': 'reach_profile',
            'action': 'list',
            'format': 1,
            'filter:serviceTypeEqual': '1',  # Machine Captioning
        }
        
        profile_response = requests.post(f'{SERVICE_URL}/api_v3/service/reach_profile/action/list', data=profile_params)
        profile_data = profile_response.json()
        reach_profile_id = profile_data.get('objects', [{}])[0].get('id', '1')
        
        # Create reach vendor catalog item
        reach_params = {
            'ks': ks,
            'service': 'reach_vendor_catalog_item',
            'action': 'add',
            'format': 1,
            'vendorCatalogItem:serviceType': '1',
            'vendorCatalogItem:sourceLanguage': 'English',
            'vendorCatalogItem:targetLanguage': 'English',
            'vendorCatalogItem:turnAroundTime': '0',
            'vendorCatalogItem:allowResubmission': 'true',
            'vendorCatalogItem:enableSpeakerChangeIndication': 'true',
            'vendorCatalogItem:enableAudioTags': 'true',
            'vendorCatalogItem:captionAssetId': caption_asset_id
        }
        
        reach_response = requests.post(f'{SERVICE_URL}/api_v3/service/reach_vendor_catalog_item/action/add', data=reach_params)
        reach_data = reach_response.json()
        
        if not reach_data.get('id'):
            print('Failed to create reach catalog item')
            return False
        
        # Submit vendor task
        import time
        task_params = {
            'ks': ks,
            'service': 'reach_entry_vendor_task',
            'action': 'add',
            'format': 1,
            'entryVendorTask:entryId': entry_id,
            'entryVendorTask:catalogItemId': reach_data['id'],
            'entryVendorTask:reachProfileId': reach_profile_id,
            'entryVendorTask:serviceType': '1',
            'entryVendorTask:serviceFeature': '1',
            'entryVendorTask:deadline': int(time.time()) + 86400,
            'entryVendorTask:turnAroundTime': '0',
            'entryVendorTask:sendNotificationWhenReady': 'true'
        }
        
        task_response = requests.post(f'{SERVICE_URL}/api_v3/service/reach_entry_vendor_task/action/add', data=task_params)
        task_data = task_response.json()
        
        if task_data.get('id'):
            print('Captions requested successfully')
            return True
        
        return False
    except Exception as e:
        print(f'Caption request error: {e}')
        return False

def get_kaltura_embed_code(entry_id):
    """Get Kaltura iframe embed code for video"""
    # Generate unique player ID
    import time
    player_id = f'kaltura_player_{int(time.time() * 1000)}'
    
    iframe = f'''<iframe id="{player_id}" src="https://cdnapisec.kaltura.com/p/{PARTNER_ID}/sp/{PARTNER_ID}00/embedIframeJs/uiconf_id/24988541/partner_id/{PARTNER_ID}?iframeembed=true&playerId={player_id}&entry_id={entry_id}" width="560" height="315" allowfullscreen webkitallowfullscreen mozAllowFullScreen allow="autoplay *; fullscreen *; encrypted-media *" frameborder="0"></iframe>'''
    
    return iframe