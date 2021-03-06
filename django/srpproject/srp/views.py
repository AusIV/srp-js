from django.http import HttpResponse, HttpResponseRedirect

from django.contrib.auth.models import User

###
### General methods
###

# We need randomly generated salts. This is about 100 bits of entropy.
def generate_salt():
    import string, random   
    randomgen = random.SystemRandom()
    salt_chars = "./" + string.ascii_letters + string.digits
    return "".join([randomgen.choice(salt_chars) for i in range(0,16)])

# We want to avoid information leakage. For users that don't exist, we need salts to be consistent.
# These "fake" salts are seeded with the username and the django secret_key. They're not as random
# as true salts should be, but they should be indistinguishable to a hacker who isn't sure whether
# or not an account exists.
def generate_fake_salt(I):
    import string, random, settings, hashlib
    random.seed("%s:%s" % (I, settings.SECRET_KEY))
    salt_chars = "./" + string.ascii_letters + string.digits    
    salt = "".join([random.choice(salt_chars) for i in range(0,16)])
    return salt, int(hashlib.sha256("%s:%s" % (salt, settings.SECRET_KEY)).hexdigest(), 16)

# In upgrades, we'll need to decrypt some AES data
def decrypt(c, key, plen):
    from srp import aes
    import base64
    moo = aes.AESModeOfOperation()
    cypherkey = map(ord, key.decode("hex"))
    ciphertext = base64.b64decode(c.replace("_", "+"))
    iv = map(ord, ciphertext[:16])
    ciphertext= map(ord, ciphertext[16:])
    return moo.decrypt(ciphertext, 0, moo.modeOfOperation["CFB"], cypherkey, len(cypherkey), iv)[:plen]

def generate_verifier(salt, username, password):
    import hashlib
    x = int(hashlib.sha256(salt + hashlib.sha256("%s:%s" % (username, password)).hexdigest()).hexdigest(), 16)
    return hex(pow(2, x, 125617018995153554710546479714086468244499594888726646874671447258204721048803))[2:-1]
    
def login_page(request):
    from django.shortcuts import render_to_response
    import util
    return render_to_response('login.html', \
        {'error': "Invalid username or password" if "error" in request.GET and request.GET["error"] == '1' and not request.user.is_authenticated() else "",\
        'jsHeader': util.loginHeader("http://%s/srp-test/javascript" % request.get_host()),\
        'loginForm': util.loginForm("http://%s/srp/" % request.get_host(), "http://google.com"),\
        'loginFunction': util.loginFunction() })

def register_page(request):
    from django.shortcuts import render_to_response
    import util
    return render_to_response('login.html', \
        {'error': "Invalid username or password" if "error" in request.GET and request.GET["error"] == '1' and not request.user.is_authenticated() else "",\
        'jsHeader': util.registerHeader("http://%s/srp-test/javascript" % request.get_host()),\
        'loginForm': util.registerForm("http://%s/srp/" % request.get_host(), "http://google.com"),\
        'loginFunction': util.registerFunction() })

###
### User Registration
###

# Step 1. A client submits a username. If the username is available, we generate a salt, store it, and return it.
# Otherwise, we return an error.
def register_salt(request):
    if User.objects.filter(username=request.POST["I"]).count() > 0:
        return HttpResponse("<error>Username already in use</error>", mimetype="text/xml")
    request.session["srp_name"] = request.POST["I"]
    request.session["srp_salt"] = generate_salt()
    return HttpResponse("<salt>%s</salt>" % request.session["srp_salt"], mimetype="text/xml")
    
# Step 2. The client creates the password verifier and sends it to the server, along with a username.
def register_user(request):
    from django.contrib import auth
    from srp.models import SRPUser
    SRPUser(salt=request.session["srp_salt"], username=request.session["srp_name"], verifier=request.POST["v"]).save()
    del request.session["srp_salt"]
    del request.session["srp_name"]
    return HttpResponse("<ok/>", mimetype="text/xml");
    
# Step 3: The client initiates the login process.

###
### User Login
###

# Step 1: The user sends an identifier and public ephemeral key, A
# The server responds with the salt and public ephemeral key, B
def handshake(request):
    import random, hashlib
    from srp.models import SRPUser
    randomgen = random.SystemRandom()
    request.session["srp_I"] = request.POST["I"]
    A = int(request.POST["A"], 16)
    request.session["srp_A"] = request.POST["A"]
    g = 2
    N = 125617018995153554710546479714086468244499594888726646874671447258204721048803
    k = 88846390364205216646376352624313659232912717719075174937149043299744712465496
    upgrade = False
    if A % N == 0:
        return HttpResponse("<error>Invalid ephemeral key.</error>", mimetype="text/xml")
    else:
        try:
            user = User.objects.get(username=request.session["srp_I"])
            try:
                user = user.srpuser
                salt = user.salt
                v = int(user.verifier, 16)
            # The auth.User exists, but the SRPUser does not
            # We need to create an SRPUser to correspond to that auth.User
            # Initially, the verifier will be based on the known hash of the password
            except SRPUser.DoesNotExist:
                salt = generate_salt()
                algo, dsalt, hashpass = user.password.split("$")
                upgrade = True
                v = generate_verifier(salt, user.username, hashpass)

        # We don't want to leak that the username doesn't exist. Make up a fake salt and verifier.
        except User.DoesNotExist:
            salt, x = generate_fake_salt(request.POST["I"])            
            v = pow(g, x, N)

        # Ensure that B%N != 0
        while True:
            b = randomgen.getrandbits(32)
            B = k*v + pow(g,b,N)
            u =  int(hashlib.sha256("%s%s" % (hex(A)[2:-1],hex(B)[2:-1])).hexdigest(), 16)
            if B % N != 0 and u % N != 0: break

        # Ideally, we could return this response and then calculate M concurrently with the user
        # Unfortunately, django isn't designed to do computations after responding.
        # Maybe someone will find a way.
        S = pow(A*pow(v,u,N), b, N)
        request.session["srp_S"] = hex(S)[2:-1]
        Mstr = "%s%s%s" % (hex(A)[2:-1],hex(B)[2:-1],hex(S)[2:-1])
        request.session["srp_M"] = hashlib.sha256(Mstr).hexdigest()
        response = "<r s='%s' B='%s'%s />" % (salt, hex(B)[2:-1], " a='%s' d='%s'" % (algo, dsalt)  if upgrade else "")
    return HttpResponse(response, mimetype="text/xml")

# Step 2: The client sends its proof of S. The server confirms, and sends its proof of S.    
def verify(request):
    import hashlib
    from django.contrib.auth import login, authenticate
    user = authenticate(username=request.session["srp_I"], M=(request.POST["M"], request.session["srp_M"]))
    if user:
        response = "<M>%s</M>" % hashlib.sha256("%s%s%s" % (request.session["srp_A"], request.session["srp_M"], request.session["srp_S"])).hexdigest()
        login(request, user)
    else:
        response = "<error>Invalid username or password.</error>"

    try:
        del request.session["srp_I"]
        del request.session["srp_M"]
        del request.session["srp_S"]
        del request.session["srp_A"]
    except KeyError:
        pass
    return HttpResponse(response, mimetype="text/xml")

# Check that the user has generated the correct M
def upgrade_auth(request):
    import hashlib
    if request.POST["M"] == request.session["srp_M"]:
        response = "<M>%s</M>" % hashlib.sha256("%s%s%s" % (request.session["srp_A"], request.session["srp_M"], request.session["srp_S"])).hexdigest()
        request.session["srp_preauth"] = True
    else:
        response = "<error>Invalid username or password.</error>"
    return HttpResponse(response, mimetype="text/xml")

# Receive the encrypted password, create the verifier, save the user, and notify the client
def upgrade_add_verifier(request):
    from srp.models import SRPUser
    from django.contrib.auth.models import User
    import hashlib
    salt = generate_salt()
    key = hashlib.sha256(request.session["srp_S"]).hexdigest()
    user = User.objects.get(username=request.session["srp_I"])
    srpuser = SRPUser()
    srpuser.__dict__.update(user.__dict__)
    srpuser.verifier = generate_verifier(salt, request.session["srp_I"], decrypt(request.POST["p"], key, int(request.POST["l"])))
    srpuser.salt = salt
    srpuser.password = ""
    srpuser.save()
    return HttpResponse("<ok/>", mimetype="text/xml")

# If a user has posted their username and password, we'll go ahead and authenticate them
def no_javascript(request):
    from django.contrib.auth.models import User
    from srp.models import SRPUser
    from django.contrib.auth import login, authenticate
    try:
        user = User.objects.get(username=request.POST["srp_username"])
        try:
            # Create a verifier for the user, and check that it matches the user's verifier
            # Since we're doing it all on one side, we can skip the rest of the protocol
            v = generate_verifier(user.srpuser.salt, request.POST["srp_username"], request.POST["srp_password"])
            user = authenticate(username=request.POST["srp_username"], M=(user.srpuser.verifier, v))
            if user:
                login(request, user)
                if not request.POST["srp_forward"].startswith("#"):
                    return HttpResponseRedirect(request.POST["srp_forward"])
                else:
                    return HttpResponseRedirect("%s%s" % (request.META["HTTP_REFERER"], request.POST["srp_forward"]))
        except SRPUser.DoesNotExist:
            # The user exists in the auth table, but not the SRP table
            # Create an SRP version of the user
            if user.check_password(request.POST["srp_password"]):
                srpuser = SRPUser()
                srpuser.__dict__.update(user.__dict__)
                srpuser.salt = generate_salt()
                srpuser.verifier = generate_verifier(srpuser.salt, request.POST["srp_username"], request.POST["srp_password"])
                srpuser.password = ""
                srpuser.save()
                if not request.POST["srp_forward"].startswith("#"):
                    return HttpResponseRedirect(request.POST["srp_forward"])
                else:
                    return HttpResponseRedirect("%s%s" % (request.META["HTTP_REFERER"], request.POST["srp_forward"]))
    except User.DoesNotExist:
        # The user does not exist in the auth tables
        # Send the client back to the login page with an error
        pass
    if "?" in request.META["HTTP_REFERER"]:
        if "error=1" in request.META["HTTP_REFERER"]:
            return HttpResponseRedirect("%s" % request.META["HTTP_REFERER"])
        else:
            return HttpResponseRedirect("%s&error=1" % request.META["HTTP_REFERER"])
    else:
        return HttpResponseRedirect("%s?error=1" % request.META["HTTP_REFERER"])
