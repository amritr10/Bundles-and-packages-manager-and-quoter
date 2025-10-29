import requests
import json
from bs4 import BeautifulSoup
import re

class Addlify(requests.Session):
    """
    An extension to `requests.Session`, this class is used to automate the point-and-click aspect of managing Companies and Contacts on Amplify.

    Must log in to execute any action, this is automatic upon initiation provided your details are correct. 
    
    TODO, the returns of functions have not been standardised. It is usually the response, but for specific calls might be data or even a success bool.
    """
    URL_LIST_BACKEND_USERS = r"https://store.omron.com.au/backend-portal/users" # GET
    URL_LIST_CUSTOMERS = r"https://store.omron.com.au/backend-portal/customers/all-customer-data" # GET
    URL_GET_COMPANY = r'https://store.omron.com.au/backend-portal/customers/companies/{company_id}' # GET
    URL_GET_ORDERS_BY_DATE_DETAILS =  r'https://store.omron.com.au/backend-portal/orders/dateRange?startDate={start_date}&endDate={end_date}' #Get
    URL_GET_ORDER_DETAILS_ID = r'https://store.omron.com.au/backend-portal/orders/{order_id}'  #Get
    URL_COMPANY_MANUALLY_VERIFY = r'https://store.omron.com.au/backend-portal/customers/{company_id}/manually-verify' #POST
    URL_COMPANY_CREDIT_APPLICTION = r'https://store.omron.com.au/account/credit/new-application' #POST
    URL_GET_COMPANY_CREDIT_APPLICTION_ID = r'https://store.omron.com.au/backend-portal/customers/{company_id}/credit-applications' #GET
    URL_APPROVE_COMPANY_CREDIT_APPLICTION = r'https://store.omron.com.au/backend-portal/customers/{company_id}/credit-applications/{application_id}/approve?omronId={nexus_id}]' #POST
    URL_EDIT_COMPANY_EDI = r'https://store.omron.com.au/backend-portal/customers/companies/{company_id}/integrations/edi' # PUT
    URL_LOGIN = r'https://store.omron.com.au/backend-portal/auth/login' # POST
    URL_NEW_CUSTOMER = r"https://store.omron.com.au/backend-portal/customers" # POST
    URL_ADD_CONTACT_TO_COMPANY = r'https://store.omron.com.au/backend-portal/customers/companies/{company_id}/contacts/create' # POST
    URL_DELETE_CONTACT = r'https://store.omron.com.au/backend-portal/customers/companies/{company_id}/contacts/{contact_id}' # DELETE
    URL_DELETE_COMPANY = r'https://store.omron.com.au/backend-portal/customers/{company_id}' # DELETE
    URL_ACCEPT_CONTACT_INVITE = r'https://store.omron.com.au/account/create' # POST


    # Quotes
    URL_GET_QUOTE = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/{quote_id}" # GET
    URL_NEW_QUOTE = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/create" # POST
    URL_DELETE_QUOTE = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/{quote_id}" # DELETE
    URL_ADD_ITEM_TO_QUOTE_SECTION = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/{quote_id}/sections/{section_id}/line-items" # POST
    URL_UPDATE_QUOTED_ITEM_DETAILS = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/{quote_id}/sections/{section_id}/line-items/{line_id}" # PUT
    URL_DELETE_QUOTED_ITEM = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/{quote_id}/sections/{section_id}/line-items/{line_id}" # DELETE
    URL_UPDATE_QUOTE_DETAILS = r"https://store.omron.com.au/backend-portal/customers/companies/{company_id}/quotes/{quote_id}/details" # PUT
    # Model listing from series
    URL_LIST_SERIES_MODELS = "https://store.omron.com.au/series/full-search"

    def login(self, emailAddress:str, password:str):
        """
        Logs into the Amplify portal with the provided email address and password.

        Args:
            emailAddress (str): The email address used for login.
            password (str): The password associated with the email address.

        Returns:
            tuple: A tuple containing a boolean indicating the success of the login operation and the response object.
        """
        # no special headers needed, nothing sneaky required either
        r = self.post(Addlify.URL_LOGIN, data={"emailAddress": emailAddress, "password": password})
        # {'message': 'Invalid email address or password'}
        if r.status_code == 200 and r.text:
            try:
                if r.json().get('message') == 'Success':
                    print("Login successful!")
                    self.logged_in = True
                    return True
            except json.JSONDecodeError:
                # Handle cases where response is not JSON
                print("Login failed: Invalid response from server.")
                self.logged_in = False
                return False

        print("Login failed!")
        self.logged_in = False
        return False
    
    def get_order_details_by_date(self, startDate:str, endDate:str):
        """
        Gets the order details for a given date range.
        Args:
            start_date (str): The start date of the order details to be retrieved.
            end_date (str): The end date of the order details to be retrieved.
        Returns:
            dict: A dictionary containing the order details for a given date range.
        """

        # Format the URL correctly
        url = self.URL_GET_ORDERS_BY_DATE_DETAILS.format(start_date=startDate,end_date=endDate)
        response = self.get(url)
        # response.raise_for_status()  # Optional: Raises an error for bad responses
        return response

    def require_login(self, method: callable):
        """
        A decorator to ensure that methods are executed only if the user is logged in.
        This method checks whether the user is logged in before proceeding. If the user 
        is not logged in, it sets `self.response` to None and prints a message indicating 
        that login is required. If the user is logged in, it executes the given method 
        and stores the response in `self.response`.

        Args:
            method (callable): The method to be executed if the user is logged in.

        Returns:
            callable: The wrapped method that includes the login check.
        """
        def wrapper(*args, **kwargs):
            if not self.logged_in:
                print("Not logged in. Please log in again / first.")
                self.response = None
                return None
            self.response = method(*args, **kwargs)
            return self.response
        return wrapper

    def cache_post_data(self, func):
        """
        A decorator to cache the data sent with a POST request.

        Args:
            func (function): The original POST function to be decorated.

        Returns:
            function: The decorated function that caches the POST data.
        """
        def wrapper(*args, **kwargs):
            self.post_data = kwargs.get('data', {})
            if not self.post_data:
                # try json
                self.post_data = kwargs.get('json', {})
            return func(*args, **kwargs)
        return wrapper


    def __init__(self, email:str, password:str):
        """
        Initializes an Addlify session and attempts to log in with the provided email and password. 
        This method also decorates standard HTTP methods with a login check.

        Args:
            email (str): The email address to log into Amplify.
            password (str): The password associated with the email to log into Amplify.
        """
        super().__init__()
        self.logged_in = None # bool for whether logged in or not
        
        # cached data, mostly for deugging 
        self.response = None # any request will replace this with the recieved response
        self.post_data = None # any post request will replace this with the data sent
        self.cache = {} # a bad practice, unstructured storing information as i go incase of failure and for debug
        self.companies = None # the list of known company ids - store it since to call repetitively takes 20 seconds per each
        
        # log in 
        self.logged_in = self.login(email, password)
        
        # Decorate the standard methods with the login check
        for method_name in ['get', 'post', 'put', 'delete']: #, 'head', 'options', 'patch']:
            original_method = getattr(self, method_name)
            decorated_method = self.require_login(original_method)
            setattr(self, method_name, decorated_method)
        print("Use `.response` to view the last response (GET, POST, PUT, DELETE).")
        
        # Decorate the post request again
        original_method = getattr(self, 'post')
        decorated_method = self.cache_post_data(original_method)
        setattr(self, 'post', decorated_method)
        print("Use `.post_data` to view the data or json sent in the last POST.")
    
    
    def get_company_url(self, company_id):
        return Addlify.URL_GET_COMPANY.format(company_id=company_id)


    def get_contact_url(self, company_id, contact_id):
        return Addlify.URL_DELETE_CONTACT.format(company_id=company_id, contact_id=contact_id)
    
    def get_quote_url(self, company_id, quote_id):
        quote_url = Addlify.URL_GET_QUOTE.format(company_id=company_id, quote_id=quote_id)
        return quote_url 

    ##--------------------------------------
    ## Methods for adding Amplify entities
    ##--------------------------------------    
    
    def _check_rank(self, rank:str):
        """
        Checks and validates the provided rank, ensuring it conforms to allowed values.

        Args:
            rank: A string representing the rank to be checked. Possible ranks include 
                'Unspecified', 'C-suite', 'Management', 'Operational' and their lower-case equivalents.

        Returns:
            The validated rank as a string, converted to the expected form if necessary.
            If the rank is not allowed, defaults to 'unspecified'.
        """
        ranks = {'Unspecified': 'unspecified', 'C-suite': 'c-suite', 'Management': 'management', 'Operational': 'operational'}
        allowed = list(ranks) + list(ranks.values())
        if rank not in allowed:
            print(f"rank '{rank}' not in allowed values of [{allowed}], setting to default of 'Unspecified'")
            rank = 'Unspecified'
        # give set value that Amplify expects
        if rank in list(ranks):
            return ranks[rank]
        else:
            return rank


    def add_contact(self, company_id:str, first_name:str, last_name:str, email:str, rank:str, title=None):
        """
        Adds a contact to a specified company.

        Args:
            company_id (str): The ID of the company to which the contact is being added.
            first_name (str): The first name of the contact.
            last_name (str): The last name of the contact.
            email (str): The email address of the contact.
            rank (str): The rank of the contact within the company.
            title (str, optional): The title of the contact. Defaults to None.

        Returns:
            Success: A bool. Note, to get the customer id we have to call ".get_company_info".                
        """
        rank = self._check_rank(rank)
        data = {"rank":rank, "firstName":first_name, "lastName":last_name, "emailAddress":email}
        if title:
            data['title'] = title
        r = self.post(Addlify.URL_ADD_CONTACT_TO_COMPANY.format(company_id=company_id), json=data)
        return r
        # # note, this doesn't return the new id if the user, so we need a second request to fetch that
        # if r.status_code == 200:
        #     return True
        # return False
    
    def send_contact_invite(self, company_id, contact_id):
        r = self.post(Addlify.URL_SEND_CONTACT_INVITE.format(company_id=company_id, contact_id=contact_id))
        return r
    
    def add_company(self, company_name:str, nexus_id:str=None):
        """
        Adds a company with the given company name and optional nexus ID.

        Args:
            company_name (str): The name of the company to add.
            nexus_id (str, optional): A 6-length numeric string representing the nexus ID of the company. Defaults to None.

        Returns:
            tuple: A tuple containing a boolean indicating success, and the company ID if successful; otherwise, None.
        """
        data = {"companyName":company_name}
        if nexus_id:
            assert str(nexus_id).isnumeric() and (len(nexus_id)==6), 'nexus_id must be a 6-length integer'
            data["nexusId"] = nexus_id
        # send the post
        r = self.post(Addlify.URL_NEW_CUSTOMER, data=data)
        # unpack the response
        msg = r.json()['message']
        id_ = r.json()['data']['id']
        if msg == "Company successfully created":
            return True, id_
        return False, None

    ##--------------------------------------------------------------------
    ## Fetch existing data - note, all stem from the company page request
    ##--------------------------------------------------------------------


    def list_backend_users(self):
        """
        List all Amplify users.
        """
        response = self.get(url=self.URL_LIST_BACKEND_USERS)
        lines = [l.strip() for l in response.text.split("\n")]
        users = json.loads([l for l in lines if l.find('let users')>-1][0].split("users = ")[1][:-1])
        return users


    def list_companies(self, reload:bool=False):
        """
        Lists all companies. 

        Fetches and returns a list of companies, potentially using cached data unless reloading is specified.
        The first call for this instance is cached. 

        Args:
            reload (bool): If True, forces reloading the company list from the server. Default is False.

        Returns:
            list: A list of companies retrieved from the server.
        """
        if self.companies:
            if not reload:
                print("Returning data fetched earlier, to reload the company list instead set reload=True")
                return self.companies
        print("This call can take up to 30 seconds, sorry!") 
        response = self.get(Addlify.URL_LIST_CUSTOMERS)

        self.companies = response.json()['customerData']['allCustomers']['dataSource']
        print(f"Found {len(self.companies)} companies.")
        return self.companies
        

    def get_order_details_by_id(self, orderId: str) -> dict:
        """
        Gets the order details for a given order ID by fetching the page and extracting
        field names and values. It looks for <h6> elements (e.g. "Purchase Order Number")
        and retrieves the next <p> element value (e.g. "212129726").
        
        Args:
            orderId (str): The ID of the order to be retrieved.
        
        Returns:
            dict: A dictionary with field names as keys and field values as values.
        """
        # Construct the URL using the provided order ID.
        url = self.URL_GET_ORDER_DETAILS_ID.format(order_id=orderId)
        
        # Use a header with a User-Agent in case the site needs it.
        # headers = {
        #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        #                   "(KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
        #     "Accept": "text/html"
        # }
        
        response = self.get(url)
        # Uncomment next line if you want to raise an error for a bad response
        # response.raise_for_status()
        
        # Debug: print out part of the HTML to ensure you’ve received the expected page.
        # print(response.text[:1000])
        
        html_content = response.text
        # Sometimes using a different parser helps with badly formatted HTML.
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Option A: Using a CSS selector scoped to the container that holds the fields.
        fields = {}
        for header in soup.select("div.display-fields-container h6"):
            key = header.get_text(strip=True)
            # Try to locate the following <p> tag.
            value_tag = header.find_next("p")
            value = value_tag.get_text(strip=True) if value_tag else ""
            fields[key] = value
        
        # Option B (alternative): If above still returns {} try removing the container filter.
        # Uncomment these lines to test:
        # fields = {}
        # for header in soup.find_all("h6"):
        #     key = header.get_text(strip=True)
        #     value_tag = header.find_next("p")
        #     value = value_tag.get_text(strip=True) if value_tag else ""
        #     fields[key] = value
        
        return fields

    def get_company_info(self, company_id:str):
        """
        Fetches and parses company information from a web page based on the provided company ID.

        Args:
            company_id (str): A unique identifier for the company whose information is to be retrieved.

        Returns:
            dict: A dictionary containing parsed company information extracted from the webpage.
        """
        def _get_let_lines(response):
            # get all the "let" variables defined in the script of the page
            page_lines = [r.strip() for r in response.text.split("\n")]
            start_ind = None
            for i, l in enumerate(page_lines):
                if l.startswith("<script>"):
                    if page_lines[i+1].startswith("let "):
                        start_ind = i+1
                if start_ind:
                    if l.startswith('</script>'):
                        end_ind = i-1
            if start_ind:
                return page_lines[start_ind:end_ind]
            return []

        def _extract_data_from_let_lines(let_lines):
            # turn the let lines into actual data that we can use
            data = {}
            for l in let_lines:
                name_plus, var_plus = l.split(" = ", maxsplit=1)
                name = name_plus.removeprefix("let ")
                var_str = var_plus.removesuffix(";")
                try:
                    data[name] = json.loads(var_str)
                except:
                    data[name] = var_str
            return data
        # get the company and extract the data into a dict
        url = self.get_company_url(company_id)
        response = self.get(url)
        let_lines = _get_let_lines(response)
        data = _extract_data_from_let_lines(let_lines)
        return data
    

    def delete_contact(self, company_id:str, contact_id:str):
        """
        Deletes a contact from a company by contacting the Addlify API and processing the response.

        Args:
            company_id (str): The unique identifier of the company from which to delete the contact.
            contact_id (str): The unique identifier of the contact to be deleted.

        Returns:
            bool: True if the contact was successfully deleted, False otherwise.
        """
        url = Addlify.URL_DELETE_CONTACT.format(company_id=company_id, contact_id=contact_id)
        r = self.delete(url)
        if r.json()['message'] == "Contact successfully deleted":
            return True
        return False


    def delete_company(self, company_id:str, delete_contacts_first:bool):
        """
        Delete a company by its ID, with the option to delete its associated contacts first.

        Args:
            company_id (str): The unique identifier of the company to be deleted.
            delete_contacts_first (bool): If True, all contacts associated with the company will be deleted first.

        Returns:
            bool: True if the company was successfully deleted, False otherwise.
        """
        # delete any contacts first
        if delete_contacts_first:
            company_info = self.get_company_info(company_id)
            if not company_info:
                print("No company '{company_id}' found, maybe list all companies first with '.list_companies'")
                return
            for contact in company_info['contacts']:
                contact_id = contact['id']
                self.delete_contact(company_id, contact_id)

        # delete the company
        url = Addlify.URL_DELETE_COMPANY.format(company_id=company_id)
        r = self.delete(url)
        if r.json()['message'] == "Customer successfully deleted":
            return True
        return False
    
    def accept_contact_invite(self, contact_id):
        """
        Sends a Post request to to accept company invite on behalf of the customer.

        Returns:
            dict: The JSON response from the server if the request is successful.
        
        Raises:
            requests.exceptions.RequestException: An error occurred during the request.
        """
        url = Addlify.URL_ACCEPT_CONTACT_INVITE

        payload ={
            "companyName": "auto4 invite test",
            "businessTypeId": "78dcf0a8-a405-11ec-9a1f-00d861e5865e",
            "accountEmailAddress": "theautotest4.1aomrontest@gmail.com",
            "accountFirstName": "auto234",
            "accountLastName": "test234",
            "industries": "78e0e107-a405-11ec-9a1f-00d861e5865e",
            "interests": "78e3b173-a405-11ec-9a1f-00d861e5865e",
            "accountPassword": "Amrit123#",
            "accountPasswordConfirmation": "Amrit123#",
            "billingSearchAddress": "53 Avis Avenue, Papatoetoe, Auckland 2025, New Zealand",
            # "billingCountry": "New Zealand",
            # "billingCity": "Auckland",
            # "billingState": "AUK",
            # "billingPostCode": "2025",
            # "billingAddressLine1": "53 Avis",
            # "billingAddressLine2": "Papatoetoe",
            "subscribeToNewsletter": False,
            "agreeToTermsAndConditions": True,
            "contactId": contact_id
        }
  
        response = self.post(url, json=payload)
        return response


    def update_edi_integration(self, company_id, custom_filter_value, customer_alert_email):
        """
        Sends a PUT request to update EDI integration settings for a specific company.

        Returns:
            dict: The JSON response from the server if the request is successful.
        
        Raises:
            requests.exceptions.RequestException: An error occurred during the request.
        """
        url = Addlify.URL_EDIT_COMPANY_EDI.format(company_id=company_id)

        payload = {
            "enableEdi": True,
            "customFilter": "OrderedByLoc",
            "customFilterEnabled": True,
            "customFilterValue": custom_filter_value,
            "customerAlertContactEmails": customer_alert_email,
            "deleteAfterSuccessfulProcessing": False,
            "isUsingStrictFilename": True,
            "omronAlertContactEmails": "amrit.ramadugu@omron.com,sales-nz@omron.com,murray.thomson@omron.com,mark.bichler@omron.com",
            "sftpHomeDirectory": "/home/omronftp",
            "sftpHost": "124.157.93.17",
            "sftpPort": "22",
            "sftpUsername": "omronftp",
            "sftpPassword" : "8j7h2rs"
        }

        response = self.put(url, json=payload)
        return response
        
    def manually_verify(self, company_id):
            """
            Sends a POST request to update verification status to "verified" for a specific company.

            Returns:
                dict: The JSON response from the server if the request is successful.
            

            """
            url = Addlify.URL_COMPANY_MANUALLY_VERIFY.format(company_id=company_id)
            response = self.post(url)
            return response
   
    def update_credit_application(self, company_id,nexus_id):
            """
            Sends a POST request to create an existig credit application using a nexus id.

            Returns:
                dict: The JSON response from the server if the request is successful.
            

            """
            url = Addlify.URL_COMPANY_CREDIT_APPLICTION.format(company_id=company_id,nexus_id=nexus_id)

            payload = {
                "companyId": company_id,
                "omronCustomerId": nexus_id
            }

            response = self.post(url, json=payload)
            return response
    
    def approve_credit_application(self, company_id,nexus_id,application_id):
            """
            Sends a POST request to create an existig credit application using a nexus id.

            Returns:
                dict: The JSON response from the server if the request is successful.
            

            """
            url = Addlify.URL_APPROVE_COMPANY_CREDIT_APPLICTION.format(company_id=company_id,nexus_id=nexus_id,application_id=application_id)

            payload = {
                "omronId": nexus_id
            }

            response = self.post(url, json=payload)
            return response



    def get_credit_application_detils_of_customer(self, company_id):
        """
        Sends a GET request to retrieve credit application details of a customer using the company ID.

        Returns:
            dict: The JSON response from the server if the request is successful.
        """
        # Format the URL correctly
        url = self.URL_GET_COMPANY_CREDIT_APPLICTION_ID.format(company_id=company_id)
        response = self.get(url)
        # response.raise_for_status()  # Optional: Raises an error for bad responses
        return response.json()
    

    ##-----------
    ## Quotes
    ##----------


    def new_quote(self, company_id: str, title: str, expiry_date: str, customer_contact_id: str, is_SPR: bool,
                   description="", project_id=""):
        """
        Add a new quote against a customer and contact.

        Args:
            company_id (str): The unique identifier of the company.
            title (str): The title of the quote.
            expiry_date (str): The expiry date of the order. Example syntax '2024-09-08'.
            customer_contact_id (str): The customer id, e.g. get this from "get_company_info". This is not the contact name!
            is_SPR (bool): Is this a special price request?
            description Optional(str): The description of the quote.
            project_id (str): The project id, e.g. get this from "get_company_info". This is not the project name!

        Returns:
            response: the response to the creation of the quote. This does not return the new quote id (unfortunately). Use 
            get_company_info to find this.
        """
        # create the new url
        example_date = "2024-09-08"
        assert len(expiry_date) == len(example_date), f'Expiry date must be in the format yyyy-mm-dd e.g. {example_date}'
        new_quote_url = Addlify.URL_NEW_QUOTE.format(company_id=company_id)
        # request the site so it looks like youa re starting form the quote page
        quote_info = {"projectId":project_id, "expiryDate":expiry_date, "title":title, 
                      "customerContactId":customer_contact_id, "isSpr":is_SPR, "description":description}
        headers = {'Content-Type': 'application/json'}
        response = self.post(new_quote_url, json=quote_info, headers=headers) 
        return response

    @staticmethod
    def extract_script_vars(soup, unique_text_strings: list) -> dict:
        '''
        Utility function for extracting "var" declarations from a script tag. 

        Arguments:
            unique_text_strings (list): Your list of string terms that allow the script tag to be uniquely identified from the soup.

        Returns:
            dict: A dictionary of the variable data (strings). Run eval() if you would like to unstring.     
        '''
        if not isinstance(unique_text_strings, list):
            assert 'unique_text_strings must be a list of expected text strings found in your target script tag'
        
        # find all script tags
        script_tags = soup.find_all({'script':True})

        # get the unique ones
        def contains_all(target, expected_strings):
            return all(expected_string in target for expected_string in expected_strings)
        with_strings = [s for s in script_tags if contains_all(str(s), unique_text_strings)]
        num_scripts = len(with_strings)
        if num_scripts != 1:
            raise ValueError(f'Expected a unique value. Your choice of unqique_text_strings yielded {num_scripts} script tags.')

        # extract from it
        script_str = str(with_strings[0]).strip()

        # Function to convert JavaScript values to Python values
        def convert_js_value(value):
            # If the value is wrapped in double or single quotes, it's a string
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                return value[1:-1]  # strip the quotes
            # For numbers and JSON-like objects/arrays, use eval
            try:
                return eval(value)
            except Exception:
                return value

        # Extract variable declarations using regex
        var_declaration_pattern = r'var\s+(\w+)\s*=\s*(.+?);'
        matches = re.findall(var_declaration_pattern, script_str, re.DOTALL)

        # Populate a dictionary with the variable names and their Python-converted values
        variables_dict = {}
        for var_name, var_value in matches:
            variables_dict[var_name] = convert_js_value(var_value.strip())
        return variables_dict


    def get_quote_info(self, company_id: str, quote_id: str):
        """
        Get the information for a quote.

        Args:
            company_id (str): The unique identifier of the company.
            quote_id (str): The unique identifier of the quote.

        Returns:
            dict: the quote information.
        """
        def _get_quote_body(response):
            # extract the quote information from the response text
            lines = [n.strip() for n in response.text.split("\n")]
            # get the correct line
            search_term = "var activeQuoteBody = "
            for l in lines:
                if l.startswith(search_term):
                    break
            # extract as data
            l = l.split(search_term)[-1][:-1]
            return json.loads(l)
        
        def _get_quote_participants(soup):
            # extract participants
            vars = Addlify.extract_script_vars(soup, ["var participants", "var customerContactDataSource"])
            return vars

        def _get_main_quote_data(soup):
            # extract main quote info
            vars = Addlify.extract_script_vars(soup, ['quote = {"id"'])
            return vars
        
        # request the url and get the data out of it
        quote_url = self.get_quote_url(company_id, quote_id)
        response = self.get(quote_url)
        quote_info = _get_quote_body(response)
        # update with additional quote info
        soup = BeautifulSoup(response.text, 'lxml')
        quote_info.update(_get_quote_participants(soup))
        quote_info.update(_get_main_quote_data(soup))
        return quote_info
    

    def _update_quote_line_item(self, company_id, quote_id, section_id, line_id, price, quantity, min_quantity):
        """
        Update the quote line with new quantities. See `.add_item_to_quote` for details on arguments. 
        """
        # add the quantity information (and price again)
        new_product_url = Addlify.URL_UPDATE_QUOTED_ITEM_DETAILS.format(company_id=company_id, quote_id=quote_id, section_id=section_id, line_id=line_id)
        order_data = {"pricePerUnit":price,"desiredQuantity":quantity,"minimumQuantity":min_quantity}
        order_response = self.put(new_product_url, data=order_data, )
        return order_response


    def add_item_to_quote(self, company_id, quote_id, section_id, model_id, price, quantity, min_quantity):
        """
        Add a product to a quote. Note, this both creates a new line item in the quote (which creates a new line id) 
        then updates the values for that line item (by line id.)

        Args:
            company_id (str): The unique identifier of the company.
            quote_id (str): The unique identifier of the quote (e.g. from get_company_info)
            section_id (str): The section within the quote to add to (e.g. from get_quote_info).
            model_id (str): The section within the quote to add to (this is NOT the sku or model number).
            price (float): The special price.
            quantity (int): The number to buy.
            min_quantity (int): The minimum number to buy.

        Returns:
            tuple(response, response): The response to creating a new line item (with line id) & the response to updating 
            the quantities for that line.
        """
        # add the product to the quote section
        section_url = Addlify.URL_ADD_ITEM_TO_QUOTE_SECTION.format(company_id=company_id, quote_id=quote_id, section_id=section_id)
        model_data = {'modelId':model_id, 'pricePerUnit':price}
        model_response = self.post(section_url, json=model_data, headers={'Content-Type':'application/json'})
        line_id = model_response.json()['id']
        # update the line information
        order_response = self._update_quote_line_item(company_id, quote_id, section_id, line_id, price, quantity, min_quantity)
        return model_response, order_response


    def update_quote_details(self, company_id, quote_id, existing_quote_info, title=None, description=None, expiryDate=None, projectId=None, isSpr=None, canSetAsSpr=None, 
                            customerContactId=None, teamId=None, assigneeId=None, participants:list=None):
        """
        Updates the quote details with your specified keys, existing keys for the quote are used otherwise.
        Most fields use ids and not names.

        Data types:
            str: title, description, expiryDate (format: 2024-10-19), projectId, customerContactId, teamId, assigneeId
            bool: isSpr, canSetAsSpr
            list: participants (list of user ids)
        
        Returns:
            response: the put method response.
        """
        fields = {
        "title": title,
        "description": description,
        "expiryDate": expiryDate,
        "projectId": projectId,
        "isSpr": isSpr,
        "canSetAsSpr": canSetAsSpr,
        "customerContactId": customerContactId,
        "participants": participants,
        "teamId": teamId,
        "assigneeId": assigneeId,
        }
        assert any(param is not None for param in fields.values()), "Ensure at least one of the optional fields is filled"
        ## create the default data for sending from the existing quote
        quote_info_main = json.loads(existing_quote_info['quote'])
        keep_keys = ['id', 'title', 'description', 'expiryDate', 'projectId', 'isSpr', 'canSetAsSpr', 'customerContactId'] # 'teamId', 'assigneeId', 'participants'
        quote_put_data = {}
        for keep_key in keep_keys:
            quote_put_data[keep_key] = quote_info_main[keep_key]

        # add the other keys that arent changing
        keep_keys = ['teamId', 'assigneeId']
        for keep_key in keep_keys:
            quote_put_data[keep_key] = existing_quote_info['assignee'][keep_key]
        
        ## Update with your changes
        for k,v in fields.items():
            # the particpants key needs an error check
            if k == "participants":
                if v:
                    quote_put_data["participants"] = [c for c in participants if c != quote_put_data['assigneeId']] 
                else:
                    quote_put_data["participants"] = existing_quote_info['participants']['quoteParticipants'] 
            if v:
                quote_put_data[k] = v

        # send the update
        url = Addlify.URL_UPDATE_QUOTE_DETAILS.format(company_id=company_id, quote_id=quote_id)
        response = self.put(url, json=quote_put_data)
        return response


    def delete_quote(self, company_id, quote_id):
        delete_url = Addlify.URL_DELETE_QUOTE.format(company_id=company_id, quote_id=quote_id)
        response = self.delete(delete_url)
        return response

    ##---------------------
    ## Getting model data
    ##---------------------
    

    def get_all_model_ids(self, series_map, update_progress=True):
        """
        series_map: dict mapping slug -> display name
        """
        #  ——— identical cache‐bootstrapping from before ———
        if 'series_models' not in self.cache:
            self.cache['series_models'] = {}
            all_data, failed, done = {}, [], []
            self.cache['series_models']['all_data']  = all_data
            self.cache['series_models']['failed']    = failed
            self.cache['series_models']['done']      = done
        else:
            all_data = self.cache['series_models']['all_data']
            done     = list(all_data.keys())
            failed   = []
            self.cache['series_models']['failed'] = failed
            self.cache['series_models']['done']   = done

        #  —— now loop over slug/display-name pairs ——
        for slug, series_name in series_map.items():
            if slug in done:
                continue

            if update_progress:
                print(f"  Beginning {slug}")

            # build the filter using the original series_name
            payload = {
                "restrictToSeriesNames": [series_name],
                "specificationFieldFilters": [],
                "itemsPerPage": 10000
            }

            try:
                response = self.get(
                    Addlify.URL_LIST_SERIES_MODELS,
                    params={"filter": json.dumps(payload)}
                )
            except Exception as e:
                failed.append((slug, "Exception", str(e)))
                done.append(slug)
                continue

            if response.status_code == 200:
                try:
                    data = response.json()
                    # new endpoint returns 'results'
                    all_data[slug] = data.get("results", [])
                except ValueError as je:
                    failed.append((slug, "JSONDecodeError", str(je)))
            else:
                failed.append((slug, response.status_code, response.reason))

            done.append(slug)

        return all_data, failed