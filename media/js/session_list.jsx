class SessionsList extends React.Component {
    constructor(props) {
        super(props);
        this.state = {sessions: []};
        this.ws = null;
    }

    componentDidMount() {
        this.ws = new WebSocket(
            "ws://localhost:3000/watch_list");
        // Connection opened
        this.ws.addEventListener('open', function (event) {
            console.log('opened');
        });
        
        // Listen for messages
        var that = this;
        this.ws.addEventListener('message', function (event) {
            var json = JSON.parse(event.data)
            that.onMessage(json);
        });
    }

    componentWillUnmount(){
        this.ws.close();
        this.ws = null;
    }

    onMessage(message) {
        console.log(message);
        
        if (message.command === "session_add") {
            var newSessions = this.state.sessions.slice(0);
            newSessions.push(
                             {
                                 id: message.session_id,
                                 state: 0
                             });
            this.setState({
                sessions: newSessions
            });
        } else if (message.command == "session_remove") {
            var newSessions =
            newSessions = this.state.sessions.filter((session) => 
                session.id !== message.session_id);
            this.setState({
                sessions: newSessions
            });
        }
    }

  render() {
      var listItems
      console.log("Rendering sessions: " + this.state.sessions.length);
    if (this.state.sessions.length === 0) {
      listItems = <li> no session </li>;
    } else {
        listItems = this.state.sessions.map((session) => 
          <li key={session.id}>session: {session.id}, state: {session.state}</li>
        );
    }


    return (
      <div className="shopping-list">
        <h1>Sessions List </h1>
        <ul>
            {listItems}
        </ul>
      </div>
    );
  }
}


const domContainer = document.querySelector('#like_button_container');
ReactDOM.render(<SessionsList />, domContainer);
