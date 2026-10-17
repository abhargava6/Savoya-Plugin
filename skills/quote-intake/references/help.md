---
title: Savoya quoting assistant — help
page_url: "https://claude.ai/artifact/QTmf31aDH5hn7o6pMdHYXm"
describes_release: 0.27.4
audience: everyone at Savoya
---

<!-- Written for Client Success Managers. This file is the one source for the help page
and for answers to "how does this work". It is read by every employee at the company, so
it never carries a price, a client name, a tool or script name, or anything about Savoya's
internal systems (PRD R88). Edit the answers here; the page is rendered from this file. -->

## What it does

The quoting assistant turns a client's ground-transportation request into an exact Savoya quote, then into the document you send: a PDF proposal, email copy, or both. Every number comes from Savoya's own pricing, the same figures the web app shows. The assistant never works out a price itself.

## How a quote goes

1. **You paste the client's request.** An itinerary, an RFP, a forwarded email. Anything the client sent.
2. **It finds the client and the stops.** If a client or a place is ambiguous, it asks you once, in one message.
3. **It asks two short questions.** Whether you want a rate sheet first, and whether you want it to pick the best value, show options, or price the vehicles you name.
4. **It checks vehicle availability in the city.** If the city has too few vehicles, it shows the three nearest markets and what each can add, and you choose. It never picks for you.
5. **You get the priced quote.** Every option, every leg, with the positioning time included.
6. **You refine it.** Different vehicles, headcount or hours, as often as you like.
7. **It asks one question.** Customize the quote, go on to the client document, or stop at the quote. "Just the quote" is a complete answer.
8. **Six quick questions, one at a time.** Discount, commission, cover, personalisation, map, format.
9. **You get the files.** The PDF, and the email copy if you asked for it.
10. **It asks what you would like changed.** Name it and the assistant fixes it, checks it again and hands you the new file.

## The questions it asks, and why

- **Discount.** An extra percentage discount is priced again through Savoya, so the new total is Savoya's number. It is not saved in Savoya.
- **Commission.** Shows the rate and the commission amount on the document. It does not change any total.
- **Cover.** Which cover page the PDF opens with.
- **Personalisation.** Event name, a short intro note, your contact details, a closing line.
- **Map.** Whether to include a route map in the PDF.
- **Format.** PDF, email copy, or both. You get exactly what you choose.

## What it cannot do yet

- A quote needs an identified client. Generic market rates with no client are not supported yet.
- A market with no stored rate needs a base rate from you. There is no estimate. The client's discount and fuel are applied to the rate you give, and it is not saved in Savoya.
- Real flight numbers and private-aviation details are kept as notes on the quote. Flights go in as "time to be confirmed".
- A passenger manifest with flight and seating detail is not supported yet.
- Vehicle counts for nearby markets are extra vehicles, not date-specific availability, and they are unconfirmed.
- Fuel cannot be changed in the document. To waive it, change it in Savoya and quote again.
- Document adjustments are flat amounts. A percentage change goes through a new quote.
- The email is copy and paste. The assistant does not send mail or create drafts.
- If your network blocks map services, the map falls back to a simple overview that does not show driving routes.
- Word and Excel exports exist but have not yet been proven in real use. Check them before you send.
- It needs the Savoya and Google Drive connections switched on. Saving the session record also needs your one-time agreement.

## Questions and answers

### Why did it ask which headcount to quote?
When a request gives a range, such as 50 to 75 passengers, the number of vehicles depends on which number you pick. The assistant asks first and prices that headcount. It never falls back to the capacity of a single vehicle.

### Why did it ask me for an address instead of a tour area?
When a stop such as "around the city" cannot be matched to a place Savoya knows, the assistant stops and asks you for an address. It never swaps in a different stop to get past the problem, because that changes the trip you are pricing.

### Why doesn't the quote match the rate sheet?
The rate sheet is a preview. The quote is the exact price, calculated the way the web app calculates it. For a client whose profile waives incidentals, the sheet can still show a fuel surcharge that the quote correctly leaves out. Use the quote.

### What is a base rate, and why is the client's price lower than the number I typed?
When Savoya has no stored rate for a vehicle in a market, you can give a rate to quote from. It is a base rate: the client's contracted discount and fuel are applied to it. Give the rate you want to quote from, not the cost you were quoted, or the client's price will come out lower than you expect.

### What does "additional vehicles" mean for nearby markets?
The counts are vehicles a nearby market adds on top of the home market, not that market's total fleet. They are unconfirmed and promise nothing about fulfilment. Say so when you talk to the client.

### Does a commission change the total?
No. The document shows the rate and the commission amount, calculated on the subtotal after discounts and before fuel. The option total stays exactly as Savoya returned it.

### Why was no email drafted when I asked only for the PDF?
You get the formats you ask for. If you ask for the PDF only, the assistant does not draft or paste an email. It offers one in a single line, and you can say yes at any time.

### How do I change an option after the PDF is made?
At "Anything you'd like changed?" say what to change. The assistant adjusts the quote, makes the file again, checks it and hands you the new one. A discount goes back through Savoya's pricing.

### Why does my map look like a diagram without roads?
Map services are public, and some company networks block them. When that happens the assistant draws an overview from the stops it already resolved and titles it "stops in order, not a driving route". It tells you which kind of map went out.

### What is saved when I finish, and who sees it?
A record of the session: the request, what was priced, the figures in the documents and anything you asked to change. It is saved to Savoya's team folder so the tool can be improved. The assistant asks once for your agreement and files the record under your name. If you say no, nothing is saved.

### What does "blocked" mean on a leg?
Savoya has no stored rate for that vehicle in that market, so it cannot price the leg. You can give a base rate to quote from, or choose another vehicle.

### How do I check my setup is working?
Say "check my quoting setup". The assistant tests the connections and tells you in plain words what is switched on and what is not.

### Can I add a discount in the PDF?
Yes. Tell the assistant the percentage and it prices the quote again through Savoya, so the document carries Savoya's own figures. Flat amounts, such as a coordinator fee, can be added as lines. The assistant does not apply percentages to a document by hand.

### What do I do when something looks wrong?
Tell the assistant "log this session" and say what looked wrong. It saves a record of the session, with or without a document, so the team can see exactly what happened. Then post a short note in the core-ideas Slack channel so someone picks it up.
