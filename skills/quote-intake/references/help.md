---
title: Savoya quoting assistant — help
page_url: "https://claude.ai/artifact/QTmf31aDH5hn7o6pMdHYXm"
describes_release: 0.27.5
audience: everyone at Savoya
---

<!-- Written for Client Success Managers. This file is the one source for the help page
and for answers to "how does this work". It is read by every employee at the company, so
it never carries a price, a client name, a tool or script name, or anything about Savoya's
internal systems (PRD R88). Edit the answers here; the page is rendered from this file. -->

## What it does

The quoting assistant turns a client's ground-transportation request into an exact Savoya quote, then into the document you send: a PDF proposal, email copy, or both. Every number comes from Savoya's own pricing, the same figures the web app shows. The assistant never works out a price itself.

## Before you start

- **Open with "Use savoya plugin to quote".** Put it at the start of your first message, then paste the request. It tells the assistant which tool to use.
- **Put the client ID in the request, and full street addresses where you have them.** With both, the assistant matches the client and every stop on the first try and asks you fewer questions. A partial address is the usual reason it stops to ask.
- **New client that is not in Savoya yet?** Quote under an existing client that has no discount. Check two places first: no discount on the company, and no discount on that client's profile. The assistant checks the quote too and stops if it shows a contracted discount. The document still says "Prepared for" the real client, so give the assistant the real name. Book under the real client later.
- **If the session wanders, start fresh.** When you work from the runbook and a side question pulls the assistant off its steps, open a new chat and paste the request again. That is faster than steering it back.

## How a quote goes

1. **You paste the client's request.** An itinerary, an RFP, a forwarded email. Anything the client sent.
2. **It finds the client and the stops.** If a client or a place is ambiguous, it asks you once, in one message.
3. **It asks two short questions.** Whether you want a rate sheet first, and whether you want it to pick the best value, show options, or price the vehicles you name.
4. **It checks vehicle availability in the city.** If the city has too few vehicles, it shows the three nearest markets and what each can add, and you choose. It never picks for you.
5. **You get the priced quote.** Every option, every leg, with the positioning time included.
6. **You refine it.** Different vehicles, headcount or hours, as often as you like.
7. **It asks one question.** Customize the quote, go on to the client document, or stop at the quote. When you have several options, the same question asks whether to use both or only one, and "both" comes first. "Just the quote" is a complete answer.
8. **Six quick questions, one at a time.** Discount, commission, format, cover, personalisation, map. The format comes before the cover and the map because only the PDF uses them.
9. **You get the files.** The PDF, and the email copy if you asked for it.
10. **It asks what you would like changed.** Name it and the assistant fixes it, checks it again and hands you the new file.

## The questions it asks, and why

- **Discount.** An extra percentage discount is priced again through Savoya, so the new total is Savoya's number. It is not saved in Savoya.
- **Commission.** Shows the rate and the commission amount on the document. It does not change any total.
- **Cover.** Which cover page the PDF opens with.
- **Personalisation.** Event name, a short intro note, your contact details, a closing line.
- **Map.** Whether to include a route map in the PDF.
- **Format.** PDF, email copy, or both. You get exactly what you choose.

## Before you promise a price

Once you ask for the client document, you can change the discount, add a greeter fee and give custom transfer rates. None of these exist in Savoya's system. The quote and the document show them, but the booking is priced from Savoya's records, so it can come out very different. Before you send:

- **A discount:** add it to the client's profile in Savoya.
- **A custom rate:** add the rate in Savoya.
- **A greeter you quoted outside Savoya:** leave a note on the reservation for billing and operations.

The assistant repeats this when it asks about each one, and again when it hands you the files.

## What it cannot do yet

- A quote needs an identified client. Generic market rates with no client are not supported yet.
- A market with no stored rate needs a base rate from you. There is no estimate. The client's discount and fuel are applied to the rate you give, and it is not saved in Savoya.
- Real flight numbers and private-aviation details are kept as notes on the quote. Flight details the client gave print as given; whatever they did not give reads "to be confirmed".
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

### What happens when the client asks for something Savoya cannot confirm, such as Wi-Fi on board or bottled water?
The assistant asks you, once for each request, how the document should answer: included, not included, available at extra cost, or that you will confirm. Your answer is printed beside the request. It never decides for you. Tax, gratuity and cancellation are answered by the terms already on the document.

### Can I get a copy without the commission?
Yes. Ask for a no-commission copy after the document is made. It is a separate file with the same totals and without the commission lines. Keep the first one for your own use.

### Why did it ask about a day block and an airport transfer?
When an hourly block runs across an airport transfer on the same day, the assistant asks whether the block should start after the transfer, at the client's time, or at another time, before it prices anything. With several options, each option is checked on its own.

### What if the client needs more vehicles than Savoya shows?
If a vendor has confirmed the extra vehicles, tell the assistant how many, which vendor and who confirmed. It prices the largest number Savoya accepts and then extends the quantity only; every other figure stays Savoya's. The vendor details show on the internal summary and never in a client document.

### The PDF would not generate. What now?
Ask the assistant for the printable document (HTML) instead, open it in your browser and use Print, then Save as PDF. It prints the same as the PDF. PDF generation needs your laptop set up for it, which is most likely the cause. Ask the product team to enable it so the next one works.

### The map is wrong or missing. What now?
Tell the assistant to drop the map. The document is complete without it. Map drawing also needs your laptop set up for it, so ask the product team to enable it for next time.

### How do I quote a client who is not in Savoya yet?
Use an existing client that has no discount, after checking the company and that client's profile for one. The assistant refuses to go on if the quote carries a contracted discount. The document carries the real client's name, which you give the assistant. Book under the real client later.

### Why can the booking price differ from my quote?
A discount, a greeter fee or a custom rate you gave while building the document is not stored in Savoya. Add the discount to the client's profile, add the custom rate in Savoya, or leave a reservation note for billing and operations about the greeter. Otherwise the booking is priced without them.

### The assistant went off track. What should I do?
Start a new chat, open with "Use savoya plugin to quote" and paste the request again. Side questions in the middle of a quote are the usual cause.

### What do I do when something looks wrong?
Tell the assistant "log this session" and say what looked wrong. It saves a record of the session, with or without a document, so the team can see exactly what happened. Then post a short note in the core-ideas Slack channel so someone picks it up.
