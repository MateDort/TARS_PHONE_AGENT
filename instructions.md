OKay granny AI is a system I built for the elderly people, but i woild like to turn it into my own assistant TARS I cloned the repo into hear fro reference. Create the exact same system as GrannyAI but leave out the Hungarian speaking part I only need english and make the TARS's prompt load with the config so it doesnt check the prompt every time before answering but knows who it is. I made a TARS.md that contains it's personality and a Máté.md that contains my information, we can reference that in the prompt for it to read it when setting up the system. Also make parts of the config file be editable like setting humor percentage and honesty percantage so i can say set humor to 65% or ask what percantage it is on now. it can edit the config and reload it and carries on without me having stop the system. 


update we need to make sure that if another phone number calls TARS then mine it asks user if they want to talk to me and notify me about the conversation and its transcription summery but does not do anything I can ask for him to do

update:
Okay so I want to build out an agent hub for all the gemini live sessions all the live sessions when start should have a name like call with Máté (main) and call with Helen and call with Drury Hotel 

the hub should allow the agents to send messages to each other from other live sessions like lets say I am talking to Tars in Mate (main) call and in the mean time TARS in my behalf is trying to get an appointment for a barber in barber shop call the original wanted appointment is 6pm but they would rather do 7pm TARS can send a message to TARS in Mate (main) (if available) to ask me if 7pm works. and i can answer yes that is perfect so TARS Mate (m,ain) sends a message back to TARS barber shop call that it works 

in the scenario when there is no Mate(main) it can send me a message asking if it works or call me based on the config settting if it says call, message or both like with summaries

Update in teh summary call,
we already have reminder_decider _in_phone-call_or_not = true or false (or something like this) lets use that in summaries to decide if i am 
in a call with TARS if yes and Callback_repoort is set to call or both it doesnt have to call me just announce it in the call like reminders if not in the call then call me 


important notes:
for security we need to implement that if I call with the phone number 404 952 5557 that will always be Mate(main) call this call is me it has access to anything editing anything ask to call other phone numbers or send messages but other phone numbers are diferent if there is a call coming in from another number it should say something like hey this is Mate Dorts assistant TARS how can I help you? and do a conversation like when i ask him to call someone with the goal of finding out the reason of the call. and that session it can be named after the phone number should send a message to Mate(main) notifying about the call and tell me the transcription summary of the call just like if i ask TARS to call someone

only Máté(main) session has access to everything in TARS 

any other conversation the only thing they have access to is conversating with TARS they cannot set reminders call other people or ask anything that is secured information. Later we can set a pin that can tell TARS that it is Mate just from another phone but first only Tars Mate(main) has access to the main TARS 

my idea of the messages is that 
there is a router the main tars whom other live sections can send the messages to and it can see all the live sessions and route the messagee to teh right session or sessions

scenarios:
the barber scenario mentioned earlier it is simple barber shop call TARS sends a message to the router does 7pm works instead of 8pm router routes it to Mate(main) call or if no call like that sends a message to Mate(main) 

but lets say
in a scenario where mate main calls 3 diferent hotels drury hilton and suit inn to ask for prices to figure out which one is the cheapest and try to negotiate the prices down and drury hotel says 100 dollars a night and suit in says 60 per night they can both send a message back to teh router to inform the other agent about the prices they got and then they can start negotiating like i just called suite inn and they said 60 per night if you can go down to 80 i will spend the nigth there 

at the end send the end offers to mate main to ask which one he wants
this routing system should allow infinite phone calls and routings (obviusly not gonna happen but it can work very nicely)