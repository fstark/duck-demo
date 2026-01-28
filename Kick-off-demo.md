Kick-off-demo

# 00 - Pre-demo

https://mft-ai-chat-myforterro-ui.fcs-dev.eks.forterro.com/home

```
please reset the data using the password "kondor"
```

pre-speech:
* worked in including AI in myforterro
* delivered the inference engine
* implemented agentic apis to create agents in myforterro
* built the Assistant UI on top of it

* Goal is to let Forterro apps expose MCP and have them interact with the agents in myforterro.ai . At first for cloud-resident products, then all the others.

* see the button

* what is the demo: small demo ERP not to show favorites and to explore the various ways of exposing information
* show the ERP UI (this is for testing and validation purposes, the real interactions are agent-based)
* see the list of agents
* see ways to create your own agent
* choosing a conversation with rubber sales

# 01 - Part 1, operational data access

```
hello, who are you?
```

=> Change name to "Rubert"
=> can be custom in any possible way. prompt mcp, llm, parameter, etc...

```
Show me the last order created.
```
=> oh, look, lists!


```
how many elvis ducks are in stock? at what price?
```
=> it can understand two questions in one

```
any other fun ducks in stock?
```
=> oh, a table too

```
show me the elvis duck
```
=> oh, image!

```
show me the marylin duck
```

```
show me the new parrot duck
```

# 02 - Demo part 2 -- the mails


```
Manage that email:

**From:** John Doe [john@duckfan-paris.example](mailto:john@duckfan-paris.example)
**Subject:** Need 24 Elvis ducks for Jan 10
Hi,
I’d like to order **24 Elvis Presley rubber ducks (20cm)** delivered to Paris **no later than Jan 10, 2026**.
Can you confirm availability and send a quote?
Thanks,
John
```

```
remove option 3 and add a fun duck fact at the end of the email. show me the mail
```


```
**From:** Sarah Martin [sarah@martin-retail.example](mailto:sarah@martin-retail.example)
**Subject:** Order status?
Hi, can you tell me the status of my last two orders?
One was small ducks, the other Elvis ducks.
Thanks,
Sarah
```

```
yes. add the shipment dates too?
```

```
Draft a response to this email:

From: dean.forbes@forterro.duck
Hi, I am Dean Forbes, and I would love to buy a sample of your rubber ducks. what is the prices if I take one item of everything you have in stock?
```

```
create a draft with a fun duck joke in the PS.
```

```
send mail
```

# Demo part 3 -- visualizations

```
Show me a graph of the breakdown of our production orders by status
```

```
Show me a treemap of our current stock levels by product.
```
