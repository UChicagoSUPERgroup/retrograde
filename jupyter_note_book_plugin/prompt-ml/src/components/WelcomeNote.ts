import { PopupNotification } from "./PopupNotification";

export class WelcomeNote extends PopupNotification {
  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor() {
    super("welcome", false, "Welcome", [{}]);
    this.addHeader("Welcome to Retrograde");
        this.addParagraph(`Throughout this data task, the Retrograde plugin will provide information about the data and your decisions. 
        The plugin provides a series of notifications that provide different information at relevant points throughout the task. 
        This <span class="code-snippet-inline">Welcome Notification</span> provides background information about the plugin and other notifications.`);
    this.addSubheader("The Plugin Interface")
        this.addParagraph(`The plugin has two main interfaces, the side panel on the right that shows which notifications are available and the main window that provides the actual notification content. 
        You can open, close, and dismiss notifications as needed, but please note that the information changes as cells are executed`);
    this.addSubheader("Protected Data")
        this.addParagraph(`Some notifications reference protected classes, which are groups of 
        people sharing a common trait who are legally protected from being discriminated against 
        on the basis of that trait. Some common examples include race, gender, 
        and pregnancy status.`);
        this.addRawHtmlElement(document.createElement("br"));
    this.addSubheader("Remember to Check for Updates")
        this.addParagraph(`As you work, be sure to regularly check Retrograde the side panel for new notifications. 
        Notifications that that have new information that has not yet been viewed will appear in <b style="color:orange">orange</b>. 
        Notifications with information that has already been viewed can be revisited at any time by clicking on it, however, these will
        appear in <b style="color:gray">gray</b>.`)
  }

  ////////////////////////////////////////////////////////////
  // Abstractions
  // Tries to make note generation more intuitive and consistent across
  // different note types and styles.
  ////////////////////////////////////////////////////////////

  public _populateNote(): HTMLDivElement {
    var elem = document.createElement("div");
    elem.classList.add("promptMl");
    elem.style.cssText = "padding: 15px; overflow: scroll;";
    return elem;
  }

  export(): HTMLDivElement {
    return this._content; // doesn't clone, returns the actual element -- prevents the event listeners from being removed
  }
}
