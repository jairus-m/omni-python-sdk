import requests
import pyarrow as pa
import pyarrow.ipc as ipc
import io
import urllib.parse
import json
import ndjson
import base64
from typing import List, Tuple, Any

class OmniAPI:
    """
    A class to interact with the Omni API.

    This class provides methods to perform various operations such as running queries,
    managing models, topics, views, fields, and users.

    Attributes:
        api_key (str): The API key for authentication.
        base_url (str): The base URL for the API.
        headers (dict): The headers used for API requests.
    """

    def __init__(self, api_key: str, base_url: str = "https://dev.thundersalmon.com/api/unstable"):
        """
        Initialize the OmniAPI instance.
        Args:
            api_key (str): The API key for authentication.
            base_url (str, optional): The base URL for the API. Defaults to "https://dev.thundersalmon.com/api/unstable".
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def wait_query_blocking(self, remaining_job_ids: List[str]) -> Tuple[Any, bool]:
        """
        Wait for query jobs to complete.
        Args:
            remaining_job_ids (List[str]): List of job IDs to wait for.
        Returns:
            Tuple[Any, bool]: A tuple containing the response JSON and a boolean indicating if the jobs are done.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = f"{self.base_url}/query/wait"
        
        # URL encode the query parameter
        encoded_query = urllib.parse.urlencode({'job_ids': json.dumps(remaining_job_ids)})
        response = requests.get(f"{url}?{encoded_query}", headers=self.headers)
        
        if response.status_code == 200:
            # Parse NDJSON response
            response_json = ndjson.loads(response.text)
            footer = response_json[-1]
            done = footer['timed_out'] == 'false'
            return response_json, done
        else:
            response.raise_for_status()

    def run_query_blocking(self, body: dict) -> Tuple[pa.Table, List[dict]]:
        """
        Run a query and wait for its completion.
        Args:
            body (dict): The query body.
        Returns:
            Tuple[pa.Table, List[dict]]: A tuple containing the result table and field information.
        Raises:
            ValueError: If no result is found in the response.
            requests.exceptions.RequestException: If the API request fails.
        """
        url = f"{self.base_url}/query/run"
        response = requests.post(url, headers=self.headers, json=body)
    
        if response.status_code == 200:
            # Parse NDJSON response
            response_json = ndjson.loads(response.text)
            footer = response_json[-1]
            done = footer['timed_out'] == 'false'
            while not done:
                response_json, done = self.wait_query_blocking(footer['remaining_job_ids'])
            data_payload = next((data_payload for data_payload in response_json if "result" in data_payload), None)
            if data_payload is not None:
                base64_data = data_payload['result']
                raw_arrow_data = base64.b64decode(base64_data)
                # Read Arrow table from raw data
                buffer = io.BytesIO(raw_arrow_data)
                reader = ipc.open_stream(buffer)
                table = reader.read_all()
                return table, data_payload['summary']['fields']
            else:
                raise ValueError("No result found in the response.")
        else:
            response.raise_for_status()

    def base_model_url(self) -> str:
        """
        Get the base URL for model operations.
        Returns:
            str: The base URL for model operations.
        """
        return f"{self.base_url}/model"

    def model_url(self, model_id: str) -> str:
        """
        Get the URL for a specific model.
        Args:
            model_id (str): The ID of the model.
        Returns:
            str: The URL for the specified model.
        """
        return f"{self.base_model_url()}/{model_id}"

    def base_topic_url(self, model_id: str) -> str:
        """
        Get the base URL for topic operations.
        Args:
            model_id (str): The ID of the model.
        Returns:
            str: The base URL for topic operations.
        """
        return f"{self.base_model_url()}/{model_id}/topic"

    def topic_url(self, model_id: str, topic_name: str) -> str:
        """
        Get the URL for a specific topic.
        Args:
            model_id (str): The ID of the model.
            topic_name (str): The name of the topic.
        Returns:
            str: The URL for the specified topic.
        """
        return f"{self.base_topic_url(model_id)}/{topic_name}"

    def base_view_url(self, model_id: str) -> str:
        """
        Get the base URL for view operations.
        Args:
            model_id (str): The ID of the model.
        Returns:
            str: The base URL for view operations.
        """
        return f"{self.base_model_url()}/{model_id}/view"

    def view_url(self, model_id: str, view_name: str) -> str:
        """
        Get the URL for a specific view.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view.
        Returns:
            str: The URL for the specified view.
        """
        return f"{self.base_view_url(model_id)}/{view_name}"

    def base_field_url(self, model_id: str) -> str:
        """
        Get the base URL for field operations.
        Args:
            model_id (str): The ID of the model.
        Returns:
            str: The base URL for field operations.
        """
        return f"{self.base_view_url(model_id)}/field"

    def field_url(self, model_id: str, view_name: str, field_name: str) -> str:
        """
        Get the URL for a specific field.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view.
            field_name (str): The name of the field.
        Returns:
            str: The URL for the specified field.
        """
        return f"{self.view_url(model_id, view_name)}/field/{field_name}"

    def create_model(self, connection_id: str, body: dict) -> dict:
        """
        Create a new model.
        Args:
            connection_id (str): The connection ID.
            body (dict): The model creation body.
        Returns:
            dict: The created model information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.base_model_url()
        body["connectionId"] = connection_id
        response = requests.post(url, headers=self.headers, json=body)
        return response.json()

    def create_topic(self, model_id: str, base_view_name: str, body: dict) -> dict:
        """
        Create a new topic.
        Args:
            model_id (str): The ID of the model.
            base_view_name (str): The name of the base view.
            body (dict): The topic creation body.
        Returns:
            dict: The created topic information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.base_topic_url(model_id)
        body["baseViewName"] = base_view_name
        response = requests.post(url, headers=self.headers, json=body)
        return response.json()

    def update_topic(self, model_id: str, topic_name: str, body: dict) -> dict:
        """
        Update an existing topic.
        Args:
            model_id (str): The ID of the model.
            topic_name (str): The name of the topic to update.
            body (dict): The topic update body.
        Returns:
            dict: The updated topic information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.topic_url(model_id, topic_name)
        response = requests.patch(url, headers=self.headers, json=body)
        return response.json()

    def delete_topic(self, model_id: str, topic_name: str) -> dict:
        """
        Delete a topic.
        Args:
            model_id (str): The ID of the model.
            topic_name (str): The name of the topic to delete.
        Returns:
            dict: The response from the delete operation.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.topic_url(model_id, topic_name)
        response = requests.delete(url, headers=self.headers)
        return response.json()

    def create_view(self, model_id: str, view_name: str, body: dict) -> dict:
        """
        Create a new view.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view to create.
            body (dict): The view creation body.
        Returns:
            dict: The created view information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.base_view_url(model_id)
        body["viewName"] = view_name
        response = requests.post(url, headers=self.headers, json=body)
        return response.json()

    def update_view(self, model_id: str, view_name: str, body: dict) -> dict:
        """
        Update an existing view.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view to update.
            body (dict): The view update body.
        Returns:
            dict: The updated view information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.view_url(model_id, view_name)
        body["viewName"] = view_name
        response = requests.patch(url, headers=self.headers, json=body)
        return response.json()

    def delete_view(self, model_id: str, view_name: str) -> dict:
        """
        Delete a view.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view to delete.
        Returns:
            dict: The response from the delete operation.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.view_url(model_id, view_name)
        response = requests.delete(url, headers=self.headers)
        return response.json()

    def create_field(self, model_id: str, view_name: str, field_name: str, body: dict) -> dict:
        """
        Create a new field.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view.
            field_name (str): The name of the field to create.
            body (dict): The field creation body.
        Returns:
            dict: The created field information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.base_field_url(model_id)
        body["fieldName"] = field_name
        body["viewName"] = view_name
        response = requests.post(url, headers=self.headers, json=body)
        return response.json()

    def update_field(self, model_id: str, view_name: str, field_name: str, body: dict) -> dict:
        """
        Update an existing field.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view.
            field_name (str): The name of the field to update.
            body (dict): The field update body.
        Returns:
            dict: The updated field information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.field_url(model_id, view_name, field_name)
        response = requests.patch(url, headers=self.headers, json=body)
        return response.json()

    def delete_field(self, model_id: str, view_name: str, field_name: str) -> dict:
        """
        Delete a field.
        Args:
            model_id (str): The ID of the model.
            view_name (str): The name of the view.
            field_name (str): The name of the field to delete.
        Returns:
            dict: The response from the delete operation.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = self.field_url(model_id, view_name, field_name)
        response = requests.delete(url, headers=self.headers)
        return response.json()

    def create_user(self, body: dict) -> requests.Response:
        """
        Create a new user.
        Args:
            body (dict): The user creation body.
        Returns:
            requests.Response: The response from the create operation.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = f"{self.base_url}/api/scim/v2/users"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, json=body)
        return response

    def update_user(self, id: str, body: dict) -> requests.Response:
        """
        Update an existing user.
        Args:
            id (str): The ID of the user to update.
            body (dict): The user update body.
        Returns:
            requests.Response: The response from the update operation.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = f"{self.base_url}/api/scim/v2/users/{id}"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.put(url, headers=headers, json=body)
        return response

    def find_user_by_email(self, email: str) -> requests.Response:
        """
        Find a user by email.
        Args:
            email (str): The email of the user to find.
        Returns:
            requests.Response: The response containing the user information.
        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        url = f"{self.base_url}/api/scim/v2/users"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, params={'filter': f'userName eq "{email}"'})
        return response
    
    def upsert_user(self, email:str, displayName:str, attributes:dict):
        """
        Create a new user or update an existing user's information.
        Args:
            email (str): The email address of the user.
            displayName (str): The display name for the user.
            attributes (dict): Additional attributes for the user.
        Returns:
            None
        Prints:
            Status messages about the operation's success or failure.
        """
        body ={
            "urn:omni:params:1.0:UserAttribute":self.listify(attributes)
        }
        response = self.find_user_by_email(email)
        if response.status_code == 200:
            users = response.json()['Resources']
            if len(users) == 1:
                user = users[0]
                body.update({"userName":email, "displayName":displayName})
                update_response = self.update_user(user['id'],body)
                if update_response.status_code == 200:
                    print(f"updated user id {user['id']}")
                else:
                    print(f"Error ({update_response.status_code}) updating user id {user['id']}")
            elif len(users) == 0:
                body.update({"userName":email, "displayName":displayName})
                creation_response = self.create_user(body)
                if creation_response.status_code == 201:
                    print(f'Created {email}, userid: {creation_response.json()["id"]}')
                else:
                    print(f'Error creating {email}: {creation_response.status_code}')

            elif len(users) > 1:
                print(f'{len(users)} found for {email}, no action taken')

    def delete_user(self, email):
        """
        Delete a user by their email address.
        Args:
            email (str): The email address of the user to delete.
        Returns:
            requests.Response: The response object if the user is successfully deleted.
        Prints:
            Status messages about the operation's success or failure.
        """
        users = self.find_user_by_email(email).json()['Resources']
        if len(users) == 1:
            user = users[0]
            response = self.delete_user_by_id(user['id'])
            if response.status_code == 204:
                print(f"deleted userid: {user['id']} email: {email}")
                return response
        elif len(users) > 1:
            print('found too many users for email {email}: ')
            for u in users:
                print(u['id'])
        elif len(users) == 0:
            print(f'user {email} not found')

    def delete_user_by_id(self, id:str):
        """
        Delete a user by their user ID.
        Args:
            id (str): The ID of the user to delete.
        Returns:
            requests.Response: The response object from the delete operation.
        """
        url = f"{self.base_url}/api/scim/v2/users"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.delete(f"{url}/{id}", headers=headers)
        return response

    def document_export(self, id:str)->dict:
        """
        Export a document by its ID.
        Args:
            id (str): The ID of the document to export.
        Returns:
            dict: The exported document data as a dictionary.
        """
        url = f"{self.base_url}/api/unstable/documents/{id}/export"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url,headers=headers)
        return response.json()

    def document_import(self, body:dict):
        """
        Import a document.
        Args:
            body (dict): The document data to import.
        Returns:
            requests.Response: The response object from the import operation.
        """
        url = f"{self.base_url}/api/unstable/documents/import"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.post(url,headers=headers, json=body)
        return response

    def list_folders(self, path:str='') -> dict:
        """
        List folders at the specified path.
        Args:
            path (str, optional): The path to list folders from. Defaults to an empty string.
        Returns:
            dict: A dictionary containing the list of folders.
        """
        url = f"{self.base_url}/api/unstable/folders"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, 
                                headers=headers, 
                                params={
                                    'path': path,
                                    }
                                )
        return response.json()

    def list_documents(self, folderId:str='') -> dict:
        """
        List documents in the specified folder.
        Args:
            folderId (str, optional): The ID of the folder to list documents from. Defaults to an empty string.
        Returns:
            dict: A dictionary containing the list of documents.
        """
        url = f"{self.base_url}/api/unstable/documents"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, 
                                headers=headers, 
                                params={
                                    'folderId': folderId if folderId else None,
                                    }
                                )
        return response.json() 

    @classmethod
    def listify(cls, d:dict) -> dict:
        """
        Convert string representations of lists in a dictionary to actual lists.
        Args:
            d (dict): The input dictionary.
        Returns:
            dict: A new dictionary with string representations of lists converted to actual lists.
        """
        out = {}
        for k,v in d.items():
            if '[' in v and ']' in v:
                out.update({k:[item for item in v.replace('[','').replace(']','').split(',')]})
            else:
                out.update({k:v})
        return out

    def generate_embed_url(self,body:dict) -> dict:
        """
        Generate an embed URL.
        Args:
            body (dict): The request body containing necessary information for generating the embed URL.
        Returns:
            requests.Response: The response object containing the generated embed URL.
        """
        url = f"{self.base_url}/embed/sso/generate-url"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, json=body)
        return response
