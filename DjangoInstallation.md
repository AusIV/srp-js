# Introduction #

srp-js can be set up to authenticate users in a django web application. It can be used in web applications with an existing userbase as well as new web applications. In existing web application, user accounts will be updated the first time they log in after srp-js is installed.


---

# Setup #
These instructions assume you have an existing django application. They also assume that the srp application is in your python path at 'srp', if it is elsewhere, you will need to adjust these instructions accordingly.

## settings.py ##

### Authentication Backends ###
Add the following lines to the bottom of your settings.py file:

```
AUTHENTICATION_BACKENDS = (
    'srp.backends.SRPBackend',
    'django.contrib.auth.backends.ModelBackend',
)
```

### Installed Applications ###
In the 'INSTALLED\_APPS' tuple, before your own application, add
```
'srp',
```

## urls.py ##
There are several options in urls.py. In any case, you will need to import srp.views, so at the top of the file, add

```
import srp.views
```

### Registration ###
If you want to allow users to register themselves, you will need to add the following lines:

```
    (r'^srp/register/salt/$', srp.views.register_salt),
    (r'^srp/register/user/$', srp.views.register_user),
```

Later on I will create instructions for allowing registration administrators to control registration, rather than allowing anyone to register themselves.

### Login ###
Add the following lines to allow users to log in:
```
    (r'^srp/handshake/$', srp.views.handshake),
    (r'^srp/authenticate/$', srp.views.verify),
```

### No Javascript ###
If you have a significant userbase that does not have javascript enabled, you may wish to allow traditional logins. In this case, the user will send his username and password in clear text to be authenticated, and you lose the protection of srp. It is up to the web developer to decide whether or not to allow this in favor of letting users log in without javascript enabled.

If you want to enable logins without javascript, add this line:

```
    (r'^srp/noJs/$', srp.views.no_javascript),
```

### Upgrades ###
If you are upgrading a django application with an existing userbase that you don't want to lose, you will need to add the following lines so that existing accounts can be upgraded to support SRP.

```
    (r'^srp/upgrade/authenticate/$', srp.views.upgrade_auth),
    (r'^srp/upgrade/verifier/$', srp.views.upgrade_add_verifier),
```

## HTML Documents ##
In order to use SRP, there are certain elements that must be present in your HTML documents. Utils.py has a number of functions designed to simplify the configuration of these elements. These functions can be used directly with views and templates, or you can pre-generate the code and insert it into the HTML documents.

### Javascript Headers ###
#### Login ####
You need to include the javascript headers in order to include SRP. The function util.loginHeader can be used to generate this code. It takes the following arguments:

  * jsDir - The full path to the directory containing SRP's javascript files.
  * compressed - (Default True) indicates whether to send clients the compressed javascript files or the human readable versions.

If you are upgrading an existing userbase to SRP, you need to make sure that srp\_register.(min.)js is in the same directory as srp.(min.)js.

#### Registration ####
You need to include the javascript headers in order to include SRP. The function util.registerHeader can be used to generate this code. It takes the following arguments:

  * jsDir - The full path to the directory containing SRP's javascript files.
  * compressed - (Default True) indicates whether to send clients the compressed javascript files or the human readable versions.

### Javascript Functions ###
#### Login ####
The javascript code used to call the SRP library should be written within the HTML document. It can be generated with the function util.loginFunction(), which takes no parameters.

#### Registration ####
The javascript code used to call the SRP library should be written within the HTML document. It can be generated with the function util.registerFunction(), which takes no parameters. It is in this code that any checks should be made for verifying password strength or to compare a password and confirmation password.

### Forms ###
The forms for login and registration have a few requirements for how they must be structured.
#### Login ####
The function util.loginForm can be used to generate the HTML for the login form. It takes the following parameters:
  * srp\_url - The path to the SRP application's URLs. If your django application is at http://www.yoursite.com/, then this should be http://www.yoursite.com/srp/
  * srp\_forward - The URL where users will be sent after a successful login.
  * login\_function - (Default 'login()') The name of the javascript function that will initiate the SRP login process.
  * no\_js - (Default True) If True, users who do not have javascript enabled will post their credentials in plaintext and be processed on the server. If false, they will not post their information.

#### Registration ####
The function util.registerForm can be used to generate the HTML for the login form. It takes the following parameters:
  * srp\_url - The path to the SRP application's URLs. If your django application is at http://www.yoursite.com/, then this should be http://www.yoursite.com/srp/
  * srp\_forward - The URL where users will be sent after a successful registration.
  * login\_function - (Default 'register()') The name of the javascript function that will initiate the SRP login process.

Javascript is currently required for registration, even if it is not required for login.