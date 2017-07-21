from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from functools import wraps
import urllib
import uuid
from oauth2client import client
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from .forms import UploadFileForm


ROOT_FOLDER_ID = 'AbcdEfghijkLmnopQrst-uVwxyZ'
ROOT_FOLDER_NAME = 'Testing Folder'
FOLDER_MIME = 'application/vnd.google-apps.folder'

def make_url_with_query(**kwargs):
	view_name = kwargs.pop('view_name')
	url = reverse(view_name)
	params = urllib.urlencode(kwargs)
	return url + "?{0}".format(params)

def redirect_with_query(**kwargs):
	return HttpResponseRedirect(make_url_with_query(**kwargs))

def google_oauth(view):
	"""Decorator to handle google oauth"""

	@wraps(view)
	def authenticate(*args, **kwargs):
		request = args[0]
		if 'credentials' not in request.session:
			return redirect_with_query(view_name='oauth2callback', redirect_view=view.func_name)
		credentials = client.OAuth2Credentials.from_json(request.session['credentials'])
		if credentials.access_token_expired:
			return redirect_with_query(view_name='oauth2callback', redirect_view=view.func_name)
		else:
			gauth = GoogleAuth()
			gauth.credentials = credentials
			gauth.Authorize()
			drive = GoogleDrive(gauth)
			request.google_drive = drive
			return view(*args, **kwargs)

	return authenticate

# Helper Functions

def make_query_string(parent, title=None):
	"""Make pydrive compatible query string"""

	if title:
		return "'{0}' in parents and title='{1}' and trashed=false".format(parent, title)
	else:
		return "'{0}' in parents and trashed=false".format(parent)

def has_folder_mime(to_check):
	return to_check['mimeType'] == FOLDER_MIME

def is_folder(content):
	try:
		return len(content) == 1 and has_folder_mime(content[0])
	except TypeError, IndexError:
		return False

def navigate_folder(drive, 
					directories=[], 
					index=0, 
					folder_id=ROOT_FOLDER_ID):

	folder_contents = None
	if index < len(directories):
		folder_contents = drive.ListFile({'q': make_query_string(folder_id, directories[index])}).GetList()
	else:
		folder_contents = drive.ListFile({'q': make_query_string(folder_id)}).GetList()

	while(is_folder(folder_contents)):
		folder_id = folder_contents[0]['id']
		folder_contents = navigate_folder(drive, directories, index+1, folder_id)

	return folder_contents

def file_info_dict(file_obj):
	file_info = {'id': file_obj['id'], 
				 'title': file_obj['title'], 
				 'modifiedDate': file_obj['modifiedDate'][0:10]}

	if has_folder_mime(file_obj):
		file_info['path'] = make_url_with_query(
								view_name='show_folder_contents', 
								folder_id=file_obj['id'])
	return file_info

def save_to_disk(f):
	unique_filename = uuid.uuid4()
	file_ext = f.name.split('.')[-1]
	filename = "{0}.{1}".format(unique_filename, file_ext)

	with open(filename, 'wb+') as destination:
		for chunk in f.chunks():
			destination.write(chunk)

	return filename

def handle_drive_upload(request, folder_id):
	filename = save_to_disk(request.FILES['content'])
	file_to_upload = request.google_drive.CreateFile()
	file_to_upload.SetContentFile(filename)

	# set file name
	file_to_upload['title'] = request.POST.get('name')

	# set folder name
	file_to_upload['parents'] = [{'id': folder_id}]
	file_to_upload.Upload()

# Django views

def index(request):
	return render(request, 'index.html', {})

@google_oauth
def show_folder_contents(request):
	folder_path = request.GET.get('folder_path', '')
	folder_id = request.GET.get('folder_id', '')

	if folder_id:
		contents = navigate_folder(request.google_drive, folder_id=folder_id)
		upload_folder_id = folder_id
	else:
		folders = folder_path.split('/')
		try:
			root_index = folders.index(ROOT_FOLDER_NAME)
			folders = folders[root_index+1:]
		except ValueError:
			pass
		contents = navigate_folder(request.google_drive, folders)
		upload_folder_id = contents[0]['parents'][0]['id'] if contents else ROOT_FOLDER_ID

	folder_contents = [file_info_dict(f) for f in contents]
	form = UploadFileForm()
	
	return render(request, 'folder_contents.html', {'folder_contents': folder_contents, 
													'upload_folder_id': upload_folder_id,
													'form': form,})

@google_oauth
def download_file(request, file_id):
	file_to_download = request.google_drive.CreateFile({'id': file_id})
	file_ext = file_to_download['title'].split('.')[-1]
	file_name = "{0}.{1}".format(file_id, file_ext)
	file_to_download.GetContentFile(file_name, remove_bom=True)
	with open(file_name, 'rb') as f:
		response = HttpResponse(f.read(), content_type=file_to_download['mimeType'])
		response['Content-Disposition'] = 'attachment; filename="download.{0}"'.format(file_ext)
		return response

@google_oauth
def upload_file(request, folder_id):
	if request.method == 'POST':
		form = UploadFileForm(request.POST, request.FILES)
		if form.is_valid():
			handle_drive_upload(request, folder_id)
			return redirect_with_query(view_name='show_folder_contents', 
										folder_id=folder_id)

def oauth2callback(request):
	gauth = GoogleAuth()
	if not request.GET.get('code', False):
		auth_url = gauth.GetAuthUrl()
		redirect_view = request.GET.get('redirect_view', '')
		auth_url += "&state={0}".format(redirect_view) 
		return redirect(auth_url)
	else:
		code = request.GET.get('code')
		gauth.Authenticate(code)
		request.session['credentials'] = gauth.credentials.to_json()
		redirect_view = request.GET.get('state', '')
		return redirect(redirect_view)