"""Class for Box API.

To get authentication info (this eventually belongs in the docs for
this connector):

Information on Box site here: https://developer.box.com/guides/applications/custom-apps/oauth2-setup/

1. Set up Box account
2. Go to Developer console (https://app.box.com/developers/console)
3. Either select an existing app or create a new one. To create a new one:
  - Select "New App" > "Custom App" > "OAuth 2.0 with JWT"
4. View your app and select "Configuration" in the left menu
5. Scroll down to get the client id & secret, and just above it
   select OAuth2.0 with JWT (Server Authentication) and
   generate a developer token, aka "access token".
"""

import logging

import boxsdk

from parsons.etl.table import Table
from parsons.utilities.check_env import check as check_env
import tempfile

logger = logging.getLogger(__name__)

class Box(object):
    """
    Box is a file storage provider.
    `Args:`
        client_id: str
            Box client (account) id -- probably a 16-char alphanumeric.
            Not required if ``BOX_CLIENT_ID`` env variable is set.
        client_secret: str
            Box private key -- probably a 32-char alphanumeric.
            Not required if ``BOX_CLIENT_SECRET`` env variable is set.
        access_token: str
            Box developer access token -- probably a 32-char alphanumeric.
            Note that this is only valid for developer use only, and should not
            be used when creating and maintaining access for typical users.
            Not required if ''BOX_ACCESS_TOKEN'' env variable is set.
    `Returns:`
        Box class
    """

    def __init__(self, client_id=None, client_secret=None, access_token=None):
        client_id = check_env('BOX_CLIENT_ID', client_id)
        client_secret = check_env('BOX_CLIENT_SECRET', client_secret)
        access_token = check_env('BOX_ACCESS_TOKEN', access_token)

        oauth = boxsdk.OAuth2(
            client_id=client_id,
            client_secret=client_secret,
            access_token = access_token
        )
        self.client = boxsdk.Client(oauth)

    def create_folder(self, folder_name, parent_folder=None) -> str:
        """Create a Box folder

        Arglist:
            folder_name   - The name to give to the new folder
            parent_folder - The parent folder in which to create the new folder. If
                            omitted, the default folder will be used.

        Returns:
            The Box id of the newly-created folder
        """
        parent_folder = parent_folder or '0'
        subfolder = self.client.folder(parent_folder).create_subfolder(folder_name)
        return subfolder.id

    def delete_folder(self, folder_id) -> None:
        """Delete a Box folder

        Arglist:
            folder_id  - The Box id of the folder to delete.
        """
        self.client.folder(folder_id=folder_id).delete()

    def delete_file(self, file_id) -> None:
        """Delete a Box file

        Arglist:
            file_id  - The Box id of the file to delete.
        """
        self.client.file(folder_id=file_id).delete()

    def list_files(self, folder_id='0') -> Table:
        """List all Box files in a folder

        Arglist:
            folder_id  - The Box id of the folder in which to search. If omitted,
                         search in the default folder.
        Returns:
            A Parsons table of files and their attributes
        """
        return self.list_items(folder_id=folder_id, item_type='file')

    def list_folders(self, folder_id='0') -> Table:
        """List all Box folders

        Arglist:
            folder_id  - The Box id of the folder in which to search. If omitted,
                         search in the default folder.
        Returns:
            A Parsons table of folders and their attributes
        """
        return self.list_items(folder_id=folder_id, item_type='folder')

    def list_items(self, folder_id='0', item_type=None) -> Table:
        url = 'https://api.box.com/2.0/folders/' + folder_id
        json_response = self.client.make_request('GET', url)

        items = Table(json_response.json()['item_collection']['entries'])
        if item_type:
            items = items.select_rows(lambda row: row.type == item_type)
        return items

    # In what formats can we upload/save Tables to Box? For now, just csv
    ALLOWED_FILE_FORMATS = ['csv']

    def upload_table(self, table, file_name, folder_id='0', format='csv') -> boxsdk.object.file.File:
        """Save the passed table to Box.

        Args:
            table      - The Parsons table to be saved
            file_name  - The filename under which it should be saved in Box
            folder_id  - Optionally, the id of the subfolder in which it should be saved
            format     - For now, only 'csv'; format in which to save table

        Returns:
            A Box File object
        """
        folder_id = folder_id or '0'

        if not format in self.ALLOWED_FILE_FORMATS:
            raise ValueError(f'Format argument to upload_table() must be in one '
                             f'of {self.ALLOWED_FILE_FORMATS}; found "{format}"')

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_file_path = temp_dir_name + '/table.csv'
            table.to_csv(local_path=temp_file_path)
            new_file = self.client.folder(folder_id).upload(file_path=temp_file_path,
                                                            file_name=file_name)
            return new_file

    def get_table(self, file_id, format='csv') -> Table:
        """Get a table that has been saved to Box in csv or JSON format.

        Args:
            file_id    - The Box file_id of the table to be retrieved
            format     - Format in which Table has been saved; for now, only 'csv'

        Returns:
            A Parsons Table
        """
        if not format in self.ALLOWED_FILE_FORMATS:
            raise ValueError(f'Format argument to upload_table() must be in one '
                             f'of {self.ALLOWED_FILE_FORMATS}; found "{format}"')

        content = self.client.file(file_id).content().decode("utf-8")
        return Table.from_csv_string(content)