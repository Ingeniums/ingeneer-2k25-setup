from datetime import datetime, timedelta

day1 = "21-05-2025"
day2 = "22-05-2025"
phases = [
    [f"{day1}T20:00", f"{day1}T21:30"],
    [f"{day1}T22:00", f"{day2}T7:30"],
    [f"{day2}T8:00", f"{day2}T15:00"],
    [f"{day2}T15:30", f"{day2}T20:00"],
]

points = {
    "warmup": 50,
    "easy": 100,
    "medium": 250,
    "hard": 400,
    "tough": 500,
}

# decay by 1/9 of the value
print("Choose difficulty:")
diffs = list(points.keys())
for i in range(len(diffs)):
    print(f"{i} - {diffs[i]}")

value = float(points[diffs[int(input("Challenge: "))]])
award = float(input("Player score: "))

for phase in phases:
    now = datetime.now()
    start = datetime.strptime(phase[0], "%d-%m-%YT%H:%M")
    end = datetime.strptime(phase[1], "%d-%m-%YT%H:%M")
    total_diff = abs(end - start)
    if  now >= start  and now <= end:
        diff = abs(now - start)
        delay = min((total_diff / 3), timedelta(hours=2))
        if diff <= delay:
            print(f"Calculated Award: {award}")
            break

        diff = diff - delay
        print(diff)
        new_value = max(value / 3, value - (((diff // timedelta(hours=1)) / 12) * value))
        print(f"Current challenge value: {new_value}")
        calculated_award = (award / value) * new_value
        print(f"Calculated award: {calculated_award}")
