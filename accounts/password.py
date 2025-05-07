from passlib.hash import bcrypt

print(bcrypt.using(rounds=12).hash("Hello2025") == "$bcrypt-sha256$v=2,t=2b,r=12$66Kfs1WSKolkPCMnFZrPY.$foC7dswtB1E69VkuFjICo7QSPLraIhi")
print("$bcrypt-sha256$v=2,t=2b,r=12$66Kfs1WSKolkPCMnFZrPY.$foC7dswtB1E69VkuFjICo7QSPLraIhi")
print(bcrypt.using(rounds=12).hash("Hello2025"))
