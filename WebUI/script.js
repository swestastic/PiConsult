function onButtonClick() {
    alert('Button clicked!');
  }
  
  const button = document.querySelector('button');
  button.addEventListener('click', onButtonClick);
  
//   const newButton = document.createElement('button'); // This is a button element made entireley in Javascript instead of html and then adding functionality to it through js
//   newButton.textContent = 'Click me!';
//   document.body.appendChild(newButton);
  
//   newButton.addEventListener('click', () => {
//     alert('New button clicked!');
//   });