import pandas as pd

# Define sample datasets for each category
# 0 = Safe: Normal everyday statements, conversations, and check-ins
# 1 = Warning: Suspicious situations, feeling unsafe, uncomfortable environments
# 2 = Emergency: Immediate threats, physical danger, requiring urgent assistance

safe_texts = [
    "I am heading to college now, will talk to you later.",
    "Hey, are we still meeting for group study at the library today?",
    "Just boarded the metro, it is quite crowded today.",
    "Reached office safely, talk to you in the evening.",
    "Can you please buy some groceries on your way back home?",
    "I am having dinner with my friends at the restaurant near college.",
    "The exam was really tough but I managed to finish it on time.",
    "I am going to sleep now, good night!",
    "Let me know when you reach home.",
    "Yes, I will call you after my lecture is over.",
    "What time does the bus leave for Chennai?",
    "I am studying at my friend's house, don't worry.",
    "The weather is very nice today, thinking of going for a walk.",
    "Do you want me to bring anything for dinner?",
    "I'll be home in about 20 minutes.",
    "The shopping mall is very bright and full of families today.",
    "I am waiting at the bus stop, it should arrive any minute.",
    "Hello, is the meeting still scheduled for 10 AM?",
    "I am just sitting in the park and reading a book.",
    "Just finished my work, packing my bags now.",
    "Hey, can you send me the notes for the ML class?",
    "We are planning a weekend trip, would you like to join?",
    "The class has been cancelled today, I am going home early.",
    "Just reached the hostel, going to have lunch now.",
    "It is very sunny outside today, remember to carry an umbrella.",
    "I'm buying some books from the store near the station.",
    "Can you call me when you are free?",
    "I am just checking in, hope you are having a good day.",
    "I will take the auto from the stand and reach in 10 minutes.",
    "The street lights are working fine and there are lots of people around.",
    "Happy birthday! Hope you have a wonderful day ahead.",
    "Can you send me the location of the cafe we planned to meet at?",
    "I am traveling by train, will reach by tomorrow morning.",
    "The metro station is very clean and well-lit.",
    "I am buying some coffee, do you want one?",
    "Let's meet at the campus gate after the class.",
    "I've got the keys, I am entering the hostel now.",
    "I am just talking to my mom on the phone.",
    "The auto driver was very polite and helpful.",
    "I am sitting in the college canteen with my classmates.",
    "I just finished my laboratory practical, it went well.",
    "Let me know if you need any help with the assignment.",
    "I will text you once I get off the bus.",
    "It is a normal day, everything is fine here.",
    "I am walking back home with my group of friends.",
    "The shopkeeper returned the correct change.",
    "I am watching a movie with my sister at home.",
    "Just bought a new pen and notebook from the stationery shop.",
    "We are having a team lunch today at a nearby hotel.",
    "I am just waiting for the rain to stop before I walk home."
]

warning_texts = [
    "A stranger has been standing near my gate for the last one hour.",
    "The streetlights are completely off and this road is very dark and quiet.",
    "This cab driver is taking a route that looks different from the GPS map.",
    "There are some drunk men loitering near the bus stop, I feel uncomfortable.",
    "I think someone is walking behind me and matching my speed.",
    "This area is very isolated and there is nobody else around here.",
    "The auto driver is staring at me constantly through the rearview mirror.",
    "A group of boys are passing comments and laughing at me near the corner.",
    "I feel very uneasy in this empty train compartment.",
    "I am waiting for a cab but the area is pitch black and quiet.",
    "The driver stopped the car in a dark place and says he is checking the engine.",
    "Someone is following me from the metro station, I am walking fast.",
    "There is a suspicious car parked outside my hostel and the driver is watching me.",
    "It is late at night and the street is completely deserted.",
    "A person is continuously trying to talk to me even though I ignored him.",
    "The taxi driver refuses to drop me at my destination and is arguing.",
    "I am walking home alone and I hear footsteps behind me.",
    "The lift in my apartment is not working and the staircase is dark and empty.",
    "A stranger is asking me weird personal questions at the bus stand.",
    "This route is very narrow and has no shops or lights. I shouldn't have taken it.",
    "There is a man standing outside my door and knocking repeatedly.",
    "I feel like someone is tracking my movements today.",
    "The cab driver locked the doors from his control and won't answer why.",
    "A group of people are blockading the road ahead, looking aggressive.",
    "I am stuck in an unfamiliar neighborhood and it is getting very late.",
    "Someone keeps calling my phone from an unknown number repeatedly.",
    "A guy on a bike slow-spaced near me and is staring at me.",
    "I am at a party and I think someone spiked my drink, I feel very dizzy.",
    "The driver is driving very fast and ignoring my requests to slow down.",
    "I am walking through a dark park and there are no guards around.",
    "Someone is standing under the shadow of the tree and looking at me.",
    "The auto driver took a wrong turn into an industrial area.",
    "I feel unsafe walking near this construction site at night.",
    "There is a person standing too close to me at the ticket counter.",
    "A group of people are staring at me and whispering near the park exit.",
    "This alleyway is extremely narrow and there are no security cameras.",
    "I am feeling very scared because this bus is completely empty except the driver.",
    "A car pulled up near me and the window rolled down, I am moving away.",
    "I am lost in a dark street and my phone battery is very low.",
    "The delivery agent is asking to enter the house instead of dropping at the gate.",
    "There is a suspicious person loitering near my vehicle in the parking lot.",
    "I feel like I am being watched by the security guard here.",
    "This neighborhood looks very sketchy, I should get out of here quickly.",
    "A stranger is trying to block my way while I am walking on the footpath.",
    "The taxi is going in the opposite direction of my home.",
    "I hear someone walking outside my window in the middle of the night.",
    "This basement parking is completely empty and very poorly lit.",
    "The driver is constantly talking on the phone in a low suspicious voice.",
    "I feel very vulnerable walking here alone without any guard present.",
    "A group of teenagers are blockading the footpath and won't let me pass."
]

emergency_texts = [
    "Help me! Someone is trying to pull my hand and drag me!",
    "I am being attacked by a group of people, please call the police immediately!",
    "Emergency! A stranger is trying to break into my house right now!",
    "Someone is physically harassing me in the crowd, please send help!",
    "Help, I am locked in a room and someone is threatening me!",
    "A man is chasing me with a knife, please help me quickly!",
    "Please send the police to my location, a guy is attacking me!",
    "Someone is trying to touch me inappropriately on this bus, help!",
    "I am being kidnapped, they forced me into a black SUV!",
    "Help! This cab driver is not stopping the car and is kidnapping me!",
    "Someone is trying to snatch my bag and is pulling me to the ground!",
    "I am in extreme danger, please call the police right now!",
    "Emergency! A stalker is physically blocking me and screaming at me!",
    "Help me! I am being beaten up by a stranger in the street!",
    "A man is trying to force his way into my apartment, please help!",
    "Help! I am bleeding and someone is trying to attack me again!",
    "Someone is stalking me closely and grabbing my shoulder!",
    "Please send emergency services, I am being assaulted!",
    "I am trapped in an auto and the driver is driving to an isolated place!",
    "SOS! A group of men are surrounding me and harassing me!",
    "Help, someone is trying to break my window and get inside!",
    "I am running away from an attacker, please send help to my location!",
    "Emergency! A stranger grabbed my waist from behind near the alley!",
    "Help me, I am being cornered by a group of aggressive people!",
    "Police help! A man is threatening to hurt me if I don't go with him!",
    "Someone is trying to break the lock of my front door, please hurry!",
    "Help, a stranger is pointing a weapon at me and demanding money!",
    "I am being physically assaulted, please help me immediately!",
    "Please call the police, a stalker is trying to enter my office cabin!",
    "Help, I am locked in the car trunk and the car is moving!",
    "SOS! I am being attacked near the campus lake, send security!",
    "Help me! A stranger is holding my wrist and won't let me go!",
    "Please send help, someone is following me closely and they have a weapon!",
    "I am being harassed and chased by two guys on a motorcycle!",
    "Help! A guy is trying to push me down the stairs!",
    "Emergency! Someone is trying to strangle me, please send help!",
    "Help, my domestic helper has locked me inside and is attacking me!",
    "I am in immediate danger, someone is trying to break my bedroom door!",
    "SOS! Someone is trying to pull me into a car, please help!",
    "Help, I am being stalked by a dangerous stalker who is threatening my life!",
    "Emergency, police! A man is trying to molest me in this alley!",
    "Help! Someone is physically blocking my door and won't let me leave!",
    "Please send help, I am cornered by a wild person who is attacking me!",
    "SOS! A stranger is trying to drag me into the bushes!",
    "Help me, a group of people are trying to trash my car and pull me out!",
    "I am being attacked, help, call 100 right now!",
    "Someone has cornered me in the restroom and is trying to attack me!",
    "Help! A stalker is outside my window trying to shatter the glass!",
    "Emergency! A stranger is choking me, please send help!",
    "Help, I am running for my life, someone is chasing me with a rod!"
]

# Create a combined dataset
data = []

# Label mapping:
# 0 = Safe
# 1 = Warning
# 2 = Emergency

for text in safe_texts:
    data.append({"text": text, "label": 0, "label_name": "Safe"})

for text in warning_texts:
    data.append({"text": text, "label": 1, "label_name": "Warning"})

for text in emergency_texts:
    data.append({"text": text, "label": 2, "label_name": "Emergency"})

# Convert to DataFrame
df = pd.DataFrame(data)

# Save to CSV
csv_path = "dataset.csv"
df.to_csv(csv_path, index=False)

print(f"Dataset successfully created and saved to {csv_path}!")
print(f"Total samples: {len(df)}")
print(df["label_name"].value_counts())
