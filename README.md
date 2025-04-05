# Dependencies
- Clone this repo
    ```sh
    $ git clone https://github.com/sjy-ok/onshape-cad-step.git
    ```
- Install dependencies
    ```sh
    $ conda create -n env_name python=2.7
    $ conda activate env_name
    $ pip install -r requirements.txt
    ```

- Fill the keys into the `creds.json` file
    ```json
    {
        "https://cad.onshape.com": {
            "access_key": "ACCESS KEY",
            "secret_key": "SECRET KEY"
        }
    }
    ```

# Usage
- Save the two compressed packages from the [ABC dataset](https://archive.nyu.edu/handle/2451/61215) to the `data/abc_objects` folder and unzip them. The directory should not contain any files except for yml files. Then run
    ```sh
    $ python process.py --link_data_folder data/abc_objects
    ```
    The results are saved in the `data/processed` folder.

- Check the latest log file. If there are models that were not downloaded, run
    ```sh
    $ python process.py --link_data_folder data/failed_{latest timestamp}
    ```
    The results are still saved in the `data/processed` folder.


# Acknowledgments
- [Onshape-public/apikey](https://github.com/onshape-public/apikey)
- [ChrisWu1997/onshape-cad-parser](https://github.com/ChrisWu1997/onshape-cad-parser)
