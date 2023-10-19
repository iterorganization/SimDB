# Connecting to the ITER remotes

## Adding the ITER remote

The commands you need to set up an ITER remote is as follows:

```shell
simdb remote config new iter https://simdb.iter.org/scenarios/api/
simdb remote config set-option iter firewall F5
```

Now when you list the remotes (using `simdb remote config list`) you should see:

```shell
...                                  
iter: https://simdb.iter.org/scenarios/api/ [firewall: F5]
...
```

You can make this your default remote using:

```shell
simdb remote config set-default iter
```

You may also want to add your ITER username to remote configuration which you can do with:

```shell
simdb remote config set-option username <ITER_USERNAME>
```

## Testing the ITER remote

Once the iter remote is set up you should be able to list simulations from ITER using:

```shell
simdb remote iter list
```

or if you have set the iter remote to be your default:

```shell
simdb remote list
```

This will ask for your username and password. To avoid having to enter your username and password
for each request you can create a SimDB token with:

```shell
simdb remote iter token new
```

