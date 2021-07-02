Alert Manager Lambda
==============================================================================

This lambda can detect all DLQ and Lambda in AWS Account that it is deployed and create a Cloudformation template based in jinja to alert it to different Response Plans.

## Prerequisites (on your computer or build server):

 * Python 3.8
   * requirements.txt file
 * Git-remote-codecommit
 * PyTest
 * VirtualEnv (recommended)


## Getting started

Clone this project onto your hard drive:

    git clone git@github.com:abejaranog/lambda_generic_alert_manager.git

Make whatever other changes are necessary, then push:

    git push origin master

## Project Diagram

![Diagram](./diagram/alert-manager.png)

## Project layout

Source code for your lambda function is in the `api` directory.
Here is the code `lambda.py` and requirements file.

Jinja alerting templates are in `api/templates`.

`template.yml` contains SAM template to deploy it.

## Testing
**Under construction**

Using pytest for testing [PyTest](https://docs.pytest.org/en/6.2.x/)

To run test, you must go to test folder and install requirements

```
pip install -r test_requirements.txt
```
and run

```
pytest
```

You must get a similar output:
```
========================================================================= test session starts ==========================================================================
platform darwin -- Python 3.9.1, pytest-6.2.4, py-1.10.0, pluggy-0.13.1
rootdir: /Users/username/path/to/yopdev-alerting-manager/test
collected 1 item                                                                                                                                                       

test_lambda.py .                                                                                                                                                 [100%]

========================================================================== 1 passed in 2.00s ===========================================================================
```


NOTE: Is strongly recommended to use a test **VirtualEnv**.



