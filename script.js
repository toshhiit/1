// Простая логика для КНБ + отправка результата на API (прототип)

let playerChoice = null;
let lastRound = null; // {player, computer, result, reward}

const choices = ["Камень","Ножницы","Бумага"];
const choiceButtons = document.querySelectorAll(".choice");
const resultBox = document.getElementById("round-result");
const sendBtn = document.getElementById("send-result");

// выбор игрока
choiceButtons.forEach(btn=>{
  btn.addEventListener("click", ()=>{
    playerChoice = btn.dataset.choice;
    playRound(playerChoice);
  });
});

function playRound(player){
  const computer = choices[Math.floor(Math.random()*3)];
  let resultText = "";
  let result = "draw";
  let reward = 0;

  if(player === computer){
    resultText = `Ничья — компьютер выбрал ${computer}.`;
    result = "draw";
    reward = 0;
  } else if(
    (player==="Камень" && computer==="Ножницы") ||
    (player==="Ножницы" && computer==="Бумага") ||
    (player==="Бумага" && computer==="Камень")
  ){
    resultText = `Победа! Компьютер выбрал ${computer}.`;
    result = "win";
    reward = 10; // пример награды
  } else {
    resultText = `Проигрыш — компьютер выбрал ${computer}.`;
    result = "lose";
    reward = 2;
  }

  lastRound = { player, computer, result, reward, game:"RPS" };
  resultBox.textContent = resultText + ` (+${reward} монет если выиграл/меньше если проиграл)`;
  sendBtn.disabled = false;
}

// Отправка результата на API (нужен бэкенд)
sendBtn.addEventListener("click", ()=>{
  if(!lastRound){
    alert("Сначала сыграй раунд.");
    return;
  }

  // Здесь должен быть реальный tg_id или токен сессии, сейчас ставим заглушку
  const payload = {
    // tg_id: 12345678,    // <- заменишь после интеграции логина
    token: getUrlParam("token") || null, // если пользователь пришёл по ?token=...
    game: lastRound.game,
    result: lastRound.result,
    reward: lastRound.reward
  };

  // пример отправки на бэкенд (замени URL на свой)
  fetch("https://adaline-noncalculating-sustainingly.ngrok-free.dev/api/game_result", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  })
  .then(r => r.json())
  .then(data=>{
    console.log("Ответ сервера:", data);
    alert("Результат отправлен. Сервер ответил: " + (data.message || JSON.stringify(data)));
    sendBtn.disabled = true;и 
  })
  .catch(err=>{
    console.warn(err);
    alert("Не удалось отправить результат. Проверь backend или URL в script.js");
  });
});

// Вспомогалка: получить параметр из URL
function getUrlParam(name){
  const u = new URL(window.location.href);
  return u.searchParams.get(name);
}
